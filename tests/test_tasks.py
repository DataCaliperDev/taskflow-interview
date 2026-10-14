# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""


def test_create_task(client, auth_headers):
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["priority"] == 2
    assert data["status"] == "todo"
    assert data["owner_id"] is not None
    assert "id" in data
    assert data["comments"] == []


def test_list_tasks(client, auth_headers, created_task):
    response = client.get(
        "/tasks/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(t["id"] == created_task["id"] and t["title"] == "Test Task" for t in data)


def test_get_task(client, auth_headers, created_task):
    response = client.get(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task["id"]
    assert data["title"] == "Test Task"
    assert data["status"] == "todo"


def test_update_task(client, auth_headers, created_task):
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task["id"]
    assert data["status"] == "in_progress"
    assert data["title"] == "Test Task"


def test_delete_task(client, auth_headers, created_task):
    response = client.delete(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"


def test_get_deleted_task(client, auth_headers, created_task):
    client.delete(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    )
    response = client.get(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_tasks_require_auth(client):
    response = client.get("/tasks/")
    assert response.status_code == 401


def test_get_missing_task(client, auth_headers):
    response = client.get("/tasks/9999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_search_tasks(client, auth_headers, created_task):
    response = client.get(
        "/tasks/search",
        params={"q": "Test"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(row["title"] == "Test Task" for row in data)


def test_add_comment(client, auth_headers, created_task):
    response = client.post(
        f"/tasks/{created_task['id']}/comments",
        json={"content": "Looks good"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Looks good"
    assert "id" in data
    assert "author_id" in data
    assert "created_at" in data

    task = client.get(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    ).json()
    assert len(task["comments"]) == 1
    assert task["comments"][0]["content"] == "Looks good"


def test_member_cannot_update_foreign_task(client, auth_headers, other_auth_headers, created_task):
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "done"},
        headers=other_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"

    original = client.get(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    ).json()
    assert original["status"] == "todo"


def test_member_cannot_delete_foreign_task(client, other_auth_headers, created_task):
    response = client.delete(
        f"/tasks/{created_task['id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_admin_can_update_any_task(client, admin_headers, created_task):
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "done"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_admin_can_delete_any_task(client, admin_headers, created_task):
    response = client.delete(
        f"/tasks/{created_task['id']}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"
