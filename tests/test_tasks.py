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
