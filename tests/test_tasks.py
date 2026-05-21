# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""

import pytest


@pytest.fixture(scope="function")
def created_task(client, test_user_token):
    """Create a task and return its full response payload. Each test gets a fresh task."""
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    return response.json()


def test_create_task(created_task):
    assert created_task["id"] is not None
    assert created_task["title"] == "Test Task"
    assert created_task["priority"] == 2
    assert created_task["status"] == "todo"


def test_list_tasks(client, test_user_token, created_task):
    response = client.get(
        "/tasks/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    ids = [t["id"] for t in response.json()]
    assert created_task["id"] in ids


def test_get_task(client, test_user_token, created_task):
    response = client.get(
        f"/tasks/{created_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == created_task["id"]


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


# Issue: no test for the search endpoint
# Issue: no test for the /summary/by-user endpoint
# Issue: no test for invalid inputs (e.g., priority=99, status="invalid")
# Issue: no test for adding/retrieving comments


# ---------------------------------------------------------------------------
# Unauthorized access — no token / invalid token
# ---------------------------------------------------------------------------

def test_list_tasks_no_token(client):
    """GET /tasks/ without a token must return 401."""
    response = client.get("/tasks/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_create_task_no_token(client):
    """POST /tasks/ without a token must return 401."""
    response = client.post("/tasks/", json={"title": "Hack", "priority": 1, "status": "todo"})
    assert response.status_code == 401


def test_get_task_no_token(client, test_user_token, created_task):
    """GET /tasks/{id} without a token must return 401."""
    response = client.get(f"/tasks/{created_task['id']}")
    assert response.status_code == 401


def test_update_task_no_token(client, test_user_token, created_task):
    """PUT /tasks/{id} without a token must return 401."""
    response = client.put(f"/tasks/{created_task['id']}", json={"status": "done"})
    assert response.status_code == 401


def test_delete_task_no_token(client, test_user_token, created_task):
    """DELETE /tasks/{id} without a token must return 401."""
    response = client.delete(f"/tasks/{created_task['id']}")
    assert response.status_code == 401


def test_endpoints_reject_invalid_token(client, test_user_token, created_task):
    """All protected /tasks endpoints must return 401 for a malformed token."""
    bad_headers = {"Authorization": "Bearer this.is.not.a.valid.jwt"}
    task_id = created_task["id"]
    assert client.get("/tasks/",            headers=bad_headers).status_code == 401
    assert client.post("/tasks/",           headers=bad_headers, json={}).status_code == 401
    assert client.get(f"/tasks/{task_id}",  headers=bad_headers).status_code == 401
    assert client.put(f"/tasks/{task_id}",  headers=bad_headers, json={}).status_code == 401
    assert client.delete(f"/tasks/{task_id}",headers=bad_headers).status_code == 401


# ---------------------------------------------------------------------------
# Helpers  (same pattern as test_users.py)
# ---------------------------------------------------------------------------

def _register(client, username, email, password="Password123"):
    r = client.post("/auth/register", json={
        "username": username, "email": email, "password": password,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _token(client, username, password="Password123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(user_id: int):
    from tests.conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    try:
        db.query(models.User).filter(models.User.id == user_id).update({"role": "admin"})
        db.commit()
    finally:
        db.close()


def _create_task(client, token, title):
    r = client.post(
        "/tasks/",
        json={"title": title, "priority": 2, "status": "todo"},
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Fixture — 1 admin + 2 members, each with their own task
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def task_auth_users(client):
    """
    Creates:
      - task_admin  (role=admin)  + task_admin_task
      - task_member_a (role=member) + task_member_a_task
      - task_member_b (role=member) + task_member_b_task
    """
    admin_data    = _register(client, "task_admin",    "task_admin@example.com")
    member_a_data = _register(client, "task_member_a", "task_member_a@example.com")
    member_b_data = _register(client, "task_member_b", "task_member_b@example.com")

    _promote_to_admin(admin_data["id"])

    admin_token    = _token(client, "task_admin")
    member_a_token = _token(client, "task_member_a")
    member_b_token = _token(client, "task_member_b")

    return {
        "admin":    {"id": admin_data["id"],    "token": admin_token,
                     "task_id": _create_task(client, admin_token,    "Admin task")},
        "member_a": {"id": member_a_data["id"], "token": member_a_token,
                     "task_id": _create_task(client, member_a_token, "Member A task")},
        "member_b": {"id": member_b_data["id"], "token": member_b_token,
                     "task_id": _create_task(client, member_b_token, "Member B task")},
    }


# ---------------------------------------------------------------------------
# Authorization test cases
# ---------------------------------------------------------------------------

def test_admin_can_edit_any_task(client, task_auth_users):
    """Admin can update a task owned by a member."""
    response = client.put(
        f"/tasks/{task_auth_users['member_a']['task_id']}",
        json={"status": "in_progress"},
        headers=_headers(task_auth_users["admin"]["token"]),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_member_can_edit_own_task(client, task_auth_users):
    """Member can update their own task."""
    response = client.put(
        f"/tasks/{task_auth_users['member_b']['task_id']}",
        json={"status": "in_progress"},
        headers=_headers(task_auth_users["member_b"]["token"]),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_member_cannot_edit_other_member_task(client, task_auth_users):
    """Member A cannot update a task owned by Member B."""
    response = client.put(
        f"/tasks/{task_auth_users['member_b']['task_id']}",
        json={"status": "done"},
        headers=_headers(task_auth_users["member_a"]["token"]),
    )
    assert response.status_code == 403


def test_member_cannot_delete_other_member_task(client, task_auth_users):
    """Member A cannot delete a task owned by Member B."""
    response = client.delete(
        f"/tasks/{task_auth_users['member_b']['task_id']}",
        headers=_headers(task_auth_users["member_a"]["token"]),
    )
    assert response.status_code == 403


def test_member_can_delete_own_task(client, task_auth_users):
    """Member can delete their own task."""
    disposable_id = _create_task(client, task_auth_users["member_a"]["token"], "Disposable task")
    response = client.delete(
        f"/tasks/{disposable_id}",
        headers=_headers(task_auth_users["member_a"]["token"]),
    )
    assert response.status_code == 200


def test_admin_can_delete_any_task(client, task_auth_users):
    """Admin can delete a task owned by a member."""
    disposable_id = _create_task(client, task_auth_users["member_b"]["token"], "Disposable task B")
    response = client.delete(
        f"/tasks/{disposable_id}",
        headers=_headers(task_auth_users["admin"]["token"]),
    )
    assert response.status_code == 200
