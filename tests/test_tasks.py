# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""

def test_create_task(client, test_user_token):
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["status"] == "todo"
    assert data["priority"] == 2
    assert data["owner_id"] > 0
    assert data["comments"] == []


def test_list_tasks(client, test_user_token, test_user_task):
    response = client.get(
        "/tasks/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == test_user_task["id"]
    assert data[0]["title"] == test_user_task["title"]
    assert data[0]["status"] == test_user_task["status"]


def test_get_task(client, test_user_token, test_user_task):
    response = client.get(
        f"/tasks/{test_user_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user_task["id"]
    assert data["title"] == test_user_task["title"]
    assert data["status"] == test_user_task["status"]
    assert data["comments"] == []


def test_update_task(client, test_user_token, test_user_task):
    response = client.put(
        f"/tasks/{test_user_task['id']}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user_task["id"]
    assert data["title"] == test_user_task["title"]
    assert data["status"] == "in_progress"
    assert data["priority"] == test_user_task["priority"]


def test_delete_task(client, test_user_token, test_user_task):
    response = client.delete(
        f"/tasks/{test_user_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"


def test_get_deleted_task(client, test_user_token, test_user_task):
    delete_response = client.delete(
        f"/tasks/{test_user_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert delete_response.status_code == 200

    response = client.get(
        f"/tasks/{test_user_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_member_cannot_update_other_user_task(client, test_user_token, admin_owned_task):
    response = client.put(
        f"/tasks/{admin_owned_task.id}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_member_cannot_delete_other_user_task(client, test_user_token, admin_owned_task):
    response = client.delete(
        f"/tasks/{admin_owned_task.id}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_admin_can_update_any_task(client, admin_user_token, member_owned_task):
    response = client.put(
        f"/tasks/{member_owned_task.id}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == member_owned_task.id
    assert data["status"] == "done"
    assert data["owner_id"] == member_owned_task.owner_id


def test_admin_can_delete_any_task(client, admin_user_token, member_delete_task):
    response = client.delete(
        f"/tasks/{member_delete_task.id}",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted"


def test_task_summary_by_user(
    client,
    admin_user_token,
    admin_user,
    member_target_user,
    test_user_token,
):
    admin_task = client.post(
        "/tasks/",
        json={"title": "Admin summary task", "priority": 2, "status": "done"},
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert admin_task.status_code == 200

    first_task = client.post(
        "/tasks/",
        json={"title": "Summary task 1", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    second_task = client.post(
        "/tasks/",
        json={"title": "Summary task 2", "priority": 2, "status": "in_progress"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert first_task.status_code == 200
    assert second_task.status_code == 200

    response = client.get(
        "/tasks/summary/by-user",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )

    assert response.status_code == 200

    rows = response.json()
    assert isinstance(rows, list)

    by_username = {row["username"]: row for row in rows}
    assert by_username[admin_user.username]["task_count"] == 1
    assert by_username["testuser"]["task_count"] == 2
    assert by_username["targetuser"]["task_count"] == 0
    assert by_username[admin_user.username]["avg_priority_score"] == 0.0
    assert by_username["testuser"]["avg_priority_score"] == 25.0


def test_search_tasks_returns_matching_rows(client, test_user_token):
    client.post(
        "/tasks/",
        json={"title": "Searchable task alpha", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    client.post(
        "/tasks/",
        json={"title": "Completely unrelated task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )

    response = client.get(
        "/tasks/search?q=alpha",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )

    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["title"] == "Searchable task alpha"


def test_add_comment_returns_created_comment(client, test_user_token, test_user, test_user_task):
    response = client.post(
        f"/tasks/{test_user_task['id']}/comments",
        json={"content": "Looks good to me"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Looks good to me"
    assert data["author_id"] == test_user.id
    assert "id" in data
    assert "created_at" in data


def test_get_task_includes_comments(client, test_user_token, test_user, test_user_task):
    comment_response = client.post(
        f"/tasks/{test_user_task['id']}/comments",
        json={"content": "First comment"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert comment_response.status_code == 200

    response = client.get(
        f"/tasks/{test_user_task['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["comments"]) == 1
    assert data["comments"][0]["content"] == "First comment"
    assert data["comments"][0]["author_id"] == test_user.id


def test_unauthorized_task_list_rejected(client):
    response = client.get("/tasks/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# Issue: no test for the search endpoint
# Issue: no test for unauthorized access (missing auth header)
# Issue: no test for invalid inputs (e.g., priority=99, status="invalid")
# Issue: no test for adding/retrieving comments
