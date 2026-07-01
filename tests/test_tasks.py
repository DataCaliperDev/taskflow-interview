# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""

import pytest
from sqlalchemy import event
from tests.conftest import engine


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
    assert response.status_code == 403


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
    assert response.status_code == 403


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
    # By this point the DB has at least 3 users (testuser, otheruser, adminuser).
    # The old N+1 implementation would fire 1 (users) + N (tasks per user) queries.
    # The new aggregation must fire exactly 2: 1 for auth + 1 LEFT JOIN aggregation.
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
    assert len(queries) == 2


# Issue: no test for the search endpoint
# Issue: no test for unauthorized access (missing auth header)
# Issue: no test for invalid inputs (e.g., priority=99, status="invalid")
# Issue: no test for adding/retrieving comments
