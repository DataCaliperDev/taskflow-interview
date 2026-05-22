# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""

import pytest


# Issue: test depends on the order in which tests run (relies on task created by test_create_task)
# Issue: no fixture or factory — tests share state via module-level variables
created_task_id = None


def test_create_task(client, test_user_token):
    global created_task_id

    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    # Issue: only checks status code, not response body structure
    assert response.status_code == 200
    created_task_id = response.json()["id"]


def test_list_tasks(client, test_user_token):
    response = client.get(
        "/tasks/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    # Issue: only asserts that the response is a list — doesn't verify contents
    assert isinstance(response.json(), list)


def test_get_task(client, test_user_token):
    # Issue: depends on test_create_task having run first
    response = client.get(
        f"/tasks/{created_task_id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_update_task(client, test_user_token):
    response = client.put(
        f"/tasks/{created_task_id}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    # Issue: no assertion on the returned status value — doesn't confirm the update was applied
    assert response.status_code == 200


def test_delete_task(client, test_user_token):
    response = client.delete(
        f"/tasks/{created_task_id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_get_deleted_task(client, test_user_token):
    response = client.get(
        f"/tasks/{created_task_id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 404


# Issue: no test for the search endpoint
# Issue: no test for the /summary/by-user endpoint
# Issue: no test for unauthorized access (missing auth header)
# Issue: no test for invalid inputs (e.g., priority=99, status="invalid")
# Issue: no test for adding/retrieving comments


# ── UC-3: ownership / admin authorisation on tasks ───────────────────────────


def _create_task_as(client, token: str, title: str = "UC3 task") -> int:
    """Helper: create a task owned by whichever user the token belongs to."""
    response = client.post(
        "/tasks/",
        json={"title": title, "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_owner_can_update_own_task(client, test_user_token):
    task_id = _create_task_as(client, test_user_token, title="owner-update")
    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_owner_can_delete_own_task(client, test_user_token):
    task_id = _create_task_as(client, test_user_token, title="owner-delete")
    response = client.delete(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_non_owner_cannot_update_task(client, test_user_token, other_user_token):
    task_id = _create_task_as(client, test_user_token, title="non-owner-update")
    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert response.status_code == 403
    # The forbidden response must not silently mutate the task.
    check = client.get(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert check.json()["status"] != "done"


def test_non_owner_cannot_delete_task(client, test_user_token, other_user_token):
    task_id = _create_task_as(client, test_user_token, title="non-owner-delete")
    response = client.delete(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert response.status_code == 403
    # The task must still exist after a forbidden delete.
    check = client.get(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert check.status_code == 200


def test_admin_can_update_other_users_task(client, test_user_token, admin_token):
    task_id = _create_task_as(client, test_user_token, title="admin-update")
    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_admin_can_delete_other_users_task(client, test_user_token, admin_token):
    task_id = _create_task_as(client, test_user_token, title="admin-delete")
    response = client.delete(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


# ── UC-5: /tasks/summary/by-user must not be N+1 ─────────────────────────────


def _summary_response_is_well_formed(payload) -> None:
    """Shared assertions on the summary endpoint's response schema."""
    assert isinstance(payload, list)
    for row in payload:
        assert set(row.keys()) == {
            "user_id",
            "username",
            "task_count",
            "avg_priority_score",
        }
        assert isinstance(row["user_id"], int)
        assert isinstance(row["username"], str)
        assert isinstance(row["task_count"], int)
        assert isinstance(row["avg_priority_score"], (int, float))


def test_summary_by_user_preserves_response_schema(client, test_user_token):
    response = client.get(
        "/tasks/summary/by-user",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    _summary_response_is_well_formed(response.json())


def test_summary_by_user_returns_correct_aggregates(client):
    """Spot-check the maths: counts and averages must match what we created.

    `calculate_priority_score(priority, status)`:
        priority * 10 * {todo: 1, in_progress: 1.5, done: 0}

    We register a brand-new user inside the test so the assertion can be
    exact — other long-lived fixture users (testuser, other_user, admin_user)
    accumulate tasks across the suite and would make a precise average
    fragile.
    """
    client.post("/auth/register", json={
        "username": "uc5_user",
        "email": "uc5_user@example.com",
        "password": "uc5passwd",  # UC-9: ≥ 8 chars
    })
    login = client.post(
        "/auth/login", data={"username": "uc5_user", "password": "uc5passwd"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create three deterministic tasks with known scores.
    # priority * 10 * status_multiplier
    client.post(
        "/tasks/",
        json={"title": "uc5-A", "priority": 1, "status": "todo"},          # 10 * 1.0 = 10
        headers=headers,
    )
    client.post(
        "/tasks/",
        json={"title": "uc5-B", "priority": 2, "status": "in_progress"},   # 20 * 1.5 = 30
        headers=headers,
    )
    client.post(
        "/tasks/",
        json={"title": "uc5-C", "priority": 3, "status": "done"},          # 30 * 0   =  0
        headers=headers,
    )
    # Expected: count=3, avg = (10 + 30 + 0) / 3 ≈ 13.33

    response = client.get("/tasks/summary/by-user", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    _summary_response_is_well_formed(rows)

    by_username = {row["username"]: row for row in rows}
    assert "uc5_user" in by_username
    me = by_username["uc5_user"]
    assert me["task_count"] == 3
    assert me["avg_priority_score"] == round((10 + 30 + 0) / 3, 2)


def test_summary_by_user_avoids_n_plus_one(
    client, test_user_token, other_user_token, admin_token, query_counter
):
    """The query count must be a small constant — NOT O(users).

    Pre-fix (N+1): 1 SELECT for users + 1 SELECT per user for tasks.
    Post-fix: 1 SELECT (LEFT OUTER JOIN), regardless of user count.

    The fixtures above guarantee that at least three users exist
    (testuser, other_user, admin_user), so a strict upper bound of `users / 2`
    is impossible to satisfy with the old N+1 implementation and gives us a
    sharp, deterministic signal.
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}

    with query_counter() as counter:
        response = client.get("/tasks/summary/by-user", headers=headers)

    assert response.status_code == 200
    rows = response.json()

    user_count = len(rows)
    assert user_count >= 3, (
        f"test pre-condition: need at least 3 users in the DB, found {user_count}"
    )

    # Tight upper bound: auth lookup (1) + the joinedload SELECT (1) = 2.
    # Allow a tiny safety margin (e.g. SQLAlchemy emitting a transaction
    # BEGIN as a separate statement on some dialects) but stay well below
    # the N+1 floor of (1 + user_count).
    assert counter["n"] <= 3, (
        f"Endpoint issued {counter['n']} SQL queries for {user_count} users — "
        f"expected ≤ 3 (a constant). The N+1 implementation would have issued "
        f"{1 + user_count}."
    )


# ── UC-9: input validation on TaskCreate / TaskUpdate ────────────────────────
# `status` is restricted to {todo, in_progress, done}; `priority` to [1, 3];
# `title` must be ≥ 1 char. Each rule is exercised with one valid and one
# invalid input, on both POST /tasks/ (create) and PUT /tasks/{id} (update),
# so a partial-update bypass is caught too.


import pytest  # noqa: E402  (kept local so we don't affect existing test order)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_task_rejects_empty_title(client, test_user_token):
    response = client.post(
        "/tasks/",
        json={"title": "", "priority": 2, "status": "todo"},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 422
    assert any("title" in err["loc"] for err in response.json()["detail"])


def test_create_task_accepts_one_character_title(client, test_user_token):
    response = client.post(
        "/tasks/",
        json={"title": "x", "priority": 2, "status": "todo"},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 200


@pytest.mark.parametrize("bad_status", ["", "TODO", "pending", "in progress", "  todo  "])
def test_create_task_rejects_invalid_status(client, test_user_token, bad_status):
    response = client.post(
        "/tasks/",
        json={"title": "valid", "priority": 2, "status": bad_status},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 422
    assert any("status" in err["loc"] for err in response.json()["detail"])


@pytest.mark.parametrize("good_status", ["todo", "in_progress", "done"])
def test_create_task_accepts_each_valid_status(client, test_user_token, good_status):
    response = client.post(
        "/tasks/",
        json={"title": "valid", "priority": 2, "status": good_status},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == good_status


@pytest.mark.parametrize("bad_priority", [0, -1, 4, 99, 100])
def test_create_task_rejects_out_of_range_priority(
    client, test_user_token, bad_priority
):
    response = client.post(
        "/tasks/",
        json={"title": "valid", "priority": bad_priority, "status": "todo"},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 422
    assert any("priority" in err["loc"] for err in response.json()["detail"])


@pytest.mark.parametrize("good_priority", [1, 2, 3])
def test_create_task_accepts_each_valid_priority(
    client, test_user_token, good_priority
):
    response = client.post(
        "/tasks/",
        json={"title": "valid", "priority": good_priority, "status": "todo"},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 200
    assert response.json()["priority"] == good_priority


def test_update_task_rejects_invalid_status(client, test_user_token):
    """Partial updates must enforce the same constraints as creation."""
    task_id = _create_task_as(client, test_user_token, title="uc9-update-status")
    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "blocked"},  # not in the allowed set
        headers=_auth(test_user_token),
    )
    assert response.status_code == 422
    assert any("status" in err["loc"] for err in response.json()["detail"])


def test_update_task_rejects_invalid_priority(client, test_user_token):
    task_id = _create_task_as(client, test_user_token, title="uc9-update-priority")
    response = client.put(
        f"/tasks/{task_id}",
        json={"priority": 5},
        headers=_auth(test_user_token),
    )
    assert response.status_code == 422
    assert any("priority" in err["loc"] for err in response.json()["detail"])


def test_update_task_allows_partial_payload(client, test_user_token):
    """Omitting a field must be allowed (no required-field error for unset keys)."""
    task_id = _create_task_as(client, test_user_token, title="uc9-update-partial")
    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "in_progress"},  # only status — title/priority omitted
        headers=_auth(test_user_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
