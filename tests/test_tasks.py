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


def test_search_tasks(client, test_user_token, created_task):
    """Search by title: matching query returns the task, non-matching query returns empty list."""
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # Query that matches the created task's title
    r = client.get("/tasks/search", params={"q": created_task["title"]}, headers=headers)
    assert r.status_code == 200
    assert any(t["title"] == created_task["title"] for t in r.json())

    # Query that matches nothing
    r = client.get("/tasks/search", params={"q": "zzz_no_match_zzz"}, headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_summary_by_user_avg_priority_score(client):
    """GET /tasks/summary/by-user returns correct avg_priority_score per user.

    Score formula (from calculate_priority_score):
      score = priority * 10 * multiplier
      multiplier: todo=1, in_progress=1.5, done=0

    User A: 1 task (priority=2, todo)  → score=20.0 → avg=20.0
    User B: 2 tasks (priority=3 in_progress → 45.0) + (priority=1 todo → 10.0) → avg=27.5
    """
    # --- setup user A ---
    _register(client, "summary_user_a", "summary_a@example.com")
    token_a = _token(client, "summary_user_a")
    client.post("/tasks/", json={"title": "A1", "priority": 2, "status": "todo"},
                headers=_headers(token_a))

    # --- setup user B ---
    _register(client, "summary_user_b", "summary_b@example.com")
    token_b = _token(client, "summary_user_b")
    client.post("/tasks/", json={"title": "B1", "priority": 3, "status": "in_progress"},
                headers=_headers(token_b))
    client.post("/tasks/", json={"title": "B2", "priority": 1, "status": "todo"},
                headers=_headers(token_b))

    # --- call summary endpoint ---
    response = client.get("/tasks/summary/by-user", headers=_headers(token_a))
    assert response.status_code == 200

    rows = {r["username"]: r for r in response.json()}

    assert rows["summary_user_a"]["avg_priority_score"] == 20.0
    assert rows["summary_user_b"]["avg_priority_score"] == 27.5

def test_add_and_retrieve_comment(client, test_user_token, created_task):
    """POST a comment on a task then verify it appears in GET /tasks/{id}."""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    task_id = created_task["id"]

    # Add a comment
    post_r = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "This is a test comment"},
        headers=headers,
    )
    assert post_r.status_code == 200
    assert post_r.json()["content"] == "This is a test comment"

    # Verify the comment appears in the task detail response
    get_r = client.get(f"/tasks/{task_id}", headers=headers)
    assert get_r.status_code == 200
    comments = get_r.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["content"] == "This is a test comment"


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


# ---------------------------------------------------------------------------
# Invalid input — POST /tasks/ and PUT /tasks/{id}
# Note: cases marked with (FAIL) currently return 200 because TaskCreate has
# no field-level validation in schemas.py — they document the missing validation.
# ---------------------------------------------------------------------------

def test_create_task_missing_title(client, test_user_token):
    """title is required — omitting it must return 422 (Pydantic enforces presence)."""
    response = client.post(
        "/tasks/",
        json={"priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 422

def test_create_task_wrong_priority_type(client, test_user_token):
    """Passing a string for priority must return 422 (Pydantic type check)."""
    response = client.post(
        "/tasks/",
        json={"title": "Wrong Type", "priority": "high", "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 422


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
