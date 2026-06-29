# tests/test_tasks.py

"""
Tests for the /tasks endpoints.

No module-global task id and no ordering assumptions: each test creates exactly
what it needs (often via the ``created_task`` fixture, which returns the task).
"""


def test_create_task(client, auth_headers):
    response = client.post(
        "/tasks/",
        json={
            "title": "Test Task",
            "description": "desc",
            "priority": 2,
            "status": "todo",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert data["title"] == "Test Task"
    assert data["description"] == "desc"
    assert data["status"] == "todo"
    assert data["priority"] == 2
    assert data["owner_id"]
    assert data["comments"] == []


def test_list_tasks(client, auth_headers, created_task):
    response = client.get("/tasks/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(t["id"] == created_task["id"] for t in data)


def test_get_task(client, auth_headers, created_task):
    response = client.get(f"/tasks/{created_task['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task["id"]
    assert data["title"] == created_task["title"]
    assert data["owner_id"] == created_task["owner_id"]


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
    # unchanged fields are preserved
    assert data["title"] == created_task["title"]


def test_delete_task(client, auth_headers, created_task):
    response = client.delete(
        f"/tasks/{created_task['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"

    # The task is really gone.
    follow = client.get(f"/tasks/{created_task['id']}", headers=auth_headers)
    assert follow.status_code == 404


# ── New tests (UC-12) ─────────────────────────────────────────────────────────

def test_get_nonexistent_task(client, auth_headers):
    response = client.get("/tasks/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_nonexistent_task(client, auth_headers):
    response = client.put(
        "/tasks/999999", json={"status": "done"}, headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_delete_nonexistent_task(client, auth_headers):
    response = client.delete("/tasks/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_create_task_without_token(client):
    response = client.post("/tasks/", json={"title": "No auth"})
    assert response.status_code == 401


def test_search_tasks(client, auth_headers):
    client.post(
        "/tasks/",
        json={"title": "Buy milk", "priority": 1, "status": "todo"},
        headers=auth_headers,
    )
    client.post(
        "/tasks/",
        json={"title": "Walk dog", "priority": 2, "status": "todo"},
        headers=auth_headers,
    )
    response = client.get("/tasks/search", params={"q": "milk"}, headers=auth_headers)
    assert response.status_code == 200
    titles = [row["title"] for row in response.json()]
    assert "Buy milk" in titles
    assert "Walk dog" not in titles


def test_add_and_retrieve_comment(client, auth_headers, created_task):
    response = client.post(
        f"/tasks/{created_task['id']}/comments",
        json={"content": "Looks good"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    comment = response.json()
    assert comment["id"]
    assert comment["content"] == "Looks good"

    # The comment is retrievable via the task detail's comments list.
    task = client.get(
        f"/tasks/{created_task['id']}", headers=auth_headers
    ).json()
    assert any(c["content"] == "Looks good" for c in task["comments"])


def test_task_summary_by_user(client, auth_headers, created_task):
    response = client.get("/tasks/summary/by-user", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    row = next(r for r in data if r["user_id"] == created_task["owner_id"])
    assert row["task_count"] >= 1
    assert "avg_priority_score" in row


def test_task_summary_aggregation_correctness(client, auth_headers, db):
    """UC-5: the summary reports exact task_count and avg_priority_score.

    Tasks are seeded directly through the db fixture with explicit owner_id,
    because ``POST /tasks/`` always assigns ``owner_id = current_user`` and so
    cannot give a *different* user tasks. The expected average is computed with
    the same ``calculate_priority_score`` the endpoint uses, so the assertion
    pins the real aggregation rather than a hand-copied magic number.
    """
    from app import models
    from app.utils.helpers import calculate_priority_score

    # A user WITH a known set of tasks of known priorities/statuses.
    busy = models.User(
        username="busyuser",
        email="busyuser@example.com",
        password_hash="x",
        role="member",
    )
    # A user with ZERO tasks.
    idle = models.User(
        username="idleuser",
        email="idleuser@example.com",
        password_hash="x",
        role="member",
    )
    db.add_all([busy, idle])
    db.commit()
    db.refresh(busy)
    db.refresh(idle)

    seeded = [
        ("todo", 3),         # 30 * 1   = 30
        ("in_progress", 2),  # 20 * 1.5 = 30
        ("done", 1),         # 10 * 0   = 0
    ]
    for status, priority in seeded:
        db.add(
            models.Task(
                title=f"{status}-{priority}",
                status=status,
                priority=priority,
                owner_id=busy.id,
            )
        )
    db.commit()

    expected_scores = [calculate_priority_score(p, s) for s, p in seeded]
    expected_avg = round(sum(expected_scores) / len(expected_scores), 2)

    response = client.get("/tasks/summary/by-user", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Response shape / keys are unchanged.
    assert isinstance(data, list)
    for row in data:
        assert set(row.keys()) == {
            "user_id",
            "username",
            "task_count",
            "avg_priority_score",
        }

    busy_row = next(r for r in data if r["user_id"] == busy.id)
    assert busy_row["username"] == "busyuser"
    assert busy_row["task_count"] == len(seeded)
    assert busy_row["avg_priority_score"] == expected_avg  # == 20.0

    idle_row = next(r for r in data if r["user_id"] == idle.id)
    assert idle_row["task_count"] == 0
    assert idle_row["avg_priority_score"] == 0


# ── UC-9: Task input validation ───────────────────────────────────────────────

def test_create_task_valid_status_and_priority(client, auth_headers):
    """A task with a valid status and priority is accepted (200)."""
    response = client.post(
        "/tasks/",
        json={"title": "Valid", "status": "in_progress", "priority": 3},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["priority"] == 3


def test_create_task_invalid_status(client, auth_headers):
    """An out-of-set status is rejected with 422."""
    response = client.post(
        "/tasks/",
        json={"title": "Bad status", "status": "invalid", "priority": 2},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "status" in str(response.json()["detail"])


def test_create_task_invalid_priority(client, auth_headers):
    """An out-of-set priority is rejected with 422."""
    response = client.post(
        "/tasks/",
        json={"title": "Bad priority", "status": "todo", "priority": 99},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "priority" in str(response.json()["detail"])


def test_create_task_empty_title(client, auth_headers):
    """An empty title is rejected with 422 (min_length=1)."""
    response = client.post(
        "/tasks/",
        json={"title": "", "status": "todo", "priority": 1},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "title" in str(response.json()["detail"])


def test_update_task_invalid_status(client, auth_headers, created_task):
    """Updating with an out-of-set status is rejected with 422."""
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "nope"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "status" in str(response.json()["detail"])


def test_update_task_partial_none_fields_ok(client, auth_headers, created_task):
    """A partial update (only priority) leaves omitted/None fields alone (200)."""
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"priority": 1},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == 1
    # status was not sent (None) and is preserved unchanged
    assert data["status"] == created_task["status"]


# ── UC-3: Task authorization ──────────────────────────────────────────────────

def test_owner_can_update_own_task(client, auth_headers, created_task):
    """The owner updates their own task → 200."""
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_owner_can_delete_own_task(client, auth_headers, created_task):
    """The owner deletes their own task → 200."""
    response = client.delete(
        f"/tasks/{created_task['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"


def test_non_owner_cannot_update_task(
    client, created_task, second_auth_headers
):
    """A different non-admin user updating someone else's task → 403."""
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "done"},
        headers=second_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"
    # The task is untouched.
    task = client.get(
        f"/tasks/{created_task['id']}", headers=second_auth_headers
    ).json()
    assert task["status"] == created_task["status"]


def test_non_owner_cannot_delete_task(
    client, created_task, second_auth_headers
):
    """A different non-admin user deleting someone else's task → 403."""
    response = client.delete(
        f"/tasks/{created_task['id']}", headers=second_auth_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"
    # The task still exists.
    follow = client.get(
        f"/tasks/{created_task['id']}", headers=second_auth_headers
    )
    assert follow.status_code == 200


def test_admin_can_update_other_users_task(
    client, created_task, admin_auth_headers
):
    """An admin updating another user's task → 200."""
    response = client.put(
        f"/tasks/{created_task['id']}",
        json={"status": "done"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_admin_can_delete_other_users_task(
    client, created_task, admin_auth_headers
):
    """An admin deleting another user's task → 200."""
    response = client.delete(
        f"/tasks/{created_task['id']}", headers=admin_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"
