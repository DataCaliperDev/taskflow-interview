# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""

from sqlalchemy import event
from tests.conftest import engine


def test_create_task(client, test_user_token):
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["priority"] == 2
    assert data["status"] == "todo"
    assert "id" in data
    assert "owner_id" in data


def test_list_tasks(client, test_user_token, created_task):
    response = client.get(
        "/tasks/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(t["id"] == created_task["id"] for t in data)


def test_get_task(client, test_user_token, created_task):
    response = client.get(
        f"/tasks/{created_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task["id"]
    assert data["title"] == created_task["title"]


def test_update_task(client, test_user_token, created_task):
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_delete_task(client, test_user_token, created_task):
    response = client.delete(
        f"/tasks/{created_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    assert "message" in response.json()


def test_get_deleted_task(client, test_user_token, created_task):
    client.delete(
        f"/tasks/{created_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    response = client.get(
        f"/tasks/{created_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 404


def test_owner_can_update_own_task(client, test_user_token):
    task = client.post(
        "/tasks/",
        json={"title": "My task"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "My updated task"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "My updated task"


def test_owner_can_delete_own_task(client, test_user_token):
    task = client.post(
        "/tasks/",
        json={"title": "Task to delete"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.delete(
        f"/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_update_task_by_non_owner_is_forbidden(client, test_user_token, other_user_token):
    task = client.post(
        "/tasks/",
        json={"title": "Owner task"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "Hijacked"},
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    # 404 rather than 403: non-owners must not be able to enumerate task IDs
    assert response.status_code == 404


def test_delete_task_by_non_owner_is_forbidden(client, test_user_token, other_user_token):
    task = client.post(
        "/tasks/",
        json={"title": "Protected task"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.delete(
        f"/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    # 404 rather than 403: non-owners must not be able to enumerate task IDs
    assert response.status_code == 404


def test_admin_can_update_any_task(client, test_user_token, admin_user_token):
    task = client.post(
        "/tasks/",
        json={"title": "Admin target"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "Admin updated"},
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200


def test_admin_can_delete_any_task(client, test_user_token, admin_user_token):
    task = client.post(
        "/tasks/",
        json={"title": "Admin delete target"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.delete(
        f"/tasks/{task['id']}",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200


def test_summary_by_user_no_n_plus_1(client, test_user_token):
    # Create 3 extra users so N+1 would fire at least 5 queries (1 auth + 1 users
    # SELECT + 4 per-user task SELECTs). The aggregation stays at 2 regardless.
    # Asserting <= 3 catches N+1 without being brittle to SQLAlchemy internals.
    for i in range(3):
        client.post("/auth/register", json={
            "username": f"extrauser{i}",
            "email": f"extra{i}@example.com",
            "password": "extrapass",
        })

    queries = []

    def on_query(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", on_query)
    try:
        response = client.get(
            "/tasks/summary/by-user",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", on_query)

    assert response.status_code == 200
    # N+1 with 4 users = 6+ queries; aggregation = 2. Ceiling of 3 distinguishes them.
    assert len(queries) <= 3


def test_list_tasks_requires_auth(client):
    response = client.get("/tasks/")
    assert response.status_code == 401


def test_get_task_not_found(client, test_user_token):
    response = client.get(
        "/tasks/99999",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 404


def test_search_tasks(client, test_user_token, created_task):
    response = client.get(
        "/tasks/search?q=Test",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert any(r["title"] == created_task["title"] for r in results)


def test_add_comment(client, test_user_token, created_task):
    response = client.post(
        f"/tasks/{created_task['id']}/comments",
        json={"content": "This is a comment"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "This is a comment"
    assert "id" in data
    assert "author_id" in data
