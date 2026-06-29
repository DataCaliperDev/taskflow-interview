"""Tests for the /tasks endpoints."""

import pytest


@pytest.fixture
def created_task(client, auth_headers):
    response = client.post(
        "/tasks/",
        json={
            "title": "Test Task",
            "priority": 2,
            "status": "todo",
            "tags": ["work", "urgent"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_task(created_task):
    assert created_task["title"] == "Test Task"
    assert created_task["priority"] == 2
    assert created_task["status"] == "todo"
    assert sorted(created_task["tags"]) == ["urgent", "work"]
    assert created_task["id"] > 0


def test_create_task_invalid_status(client, auth_headers):
    response = client.post(
        "/tasks/",
        json={"title": "Bad", "status": "invalid"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_task_invalid_priority(client, auth_headers):
    response = client.post(
        "/tasks/",
        json={"title": "Bad", "priority": 99},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_list_tasks_pagination(client, auth_headers):
    for i in range(3):
        client.post(
            "/tasks/",
            json={"title": f"Task {i}"},
            headers=auth_headers,
        )
    response = client.get("/tasks/?page=1&page_size=2", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2


def test_list_tasks_filter_by_status(client, auth_headers):
    client.post("/tasks/", json={"title": "A", "status": "todo"}, headers=auth_headers)
    client.post("/tasks/", json={"title": "B", "status": "done"}, headers=auth_headers)
    response = client.get("/tasks/?status=done", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "done"


def test_get_task(client, auth_headers, created_task):
    response = client.get(f"/tasks/{created_task['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created_task["id"]


def test_update_task_applies_change(client, auth_headers, created_task):
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_delete_task_returns_204(client, auth_headers, created_task):
    response = client.delete(f"/tasks/{created_task['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert response.content == b""
    follow_up = client.get(f"/tasks/{created_task['id']}", headers=auth_headers)
    assert follow_up.status_code == 404


def test_cannot_update_other_users_task(client, auth_headers, created_task):
    other_token = None
    client.post("/auth/register", json={
        "username": "intruder",
        "email": "intruder@example.com",
        "password": "intruder123",
    })
    other_token = client.post("/auth/login", data={
        "username": "intruder", "password": "intruder123",
    }).json()["access_token"]

    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"title": "Hijacked"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403


def test_admin_can_delete_any_task(client, auth_headers, created_task, admin_token):
    response = client.delete(
        f"/tasks/{created_task['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


def test_search_uses_response_model(client, auth_headers):
    client.post("/tasks/", json={"title": "Find me please"}, headers=auth_headers)
    response = client.get("/tasks/search?q=Find", headers=auth_headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["title"] == "Find me please"
    assert "password_hash" not in results[0]


def test_search_sql_injection_is_safe(client, auth_headers):
    client.post("/tasks/", json={"title": "Safe task"}, headers=auth_headers)
    response = client.get("/tasks/search?q=' OR '1'='1", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_summary_by_user(client, auth_headers):
    client.post("/tasks/", json={"title": "X", "priority": 3, "status": "todo"},
                headers=auth_headers)
    response = client.get("/tasks/summary/by-user", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert any(row["task_count"] >= 1 for row in data)


def test_add_and_filter_by_comment_and_tag(client, auth_headers, created_task):
    comment = client.post(
        f"/tasks/{created_task['id']}/comments",
        json={"content": "First comment"},
        headers=auth_headers,
    )
    assert comment.status_code == 201
    assert comment.json()["content"] == "First comment"

    response = client.get("/tasks/?tag=urgent", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_unauthorized_access_rejected(client):
    response = client.get("/tasks/")
    assert response.status_code == 401
