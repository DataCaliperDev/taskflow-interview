# tests/test_users.py

"""
Tests for the /users endpoints.
"""


def test_get_me(client, test_user_token):
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert data["role"] == "member"
    assert data["is_active"] is True
    assert "password_hash" not in data


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["username"] == "testuser"
    assert data[0]["email"] == "testuser@example.com"
    assert "password_hash" not in data[0]


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_user(client, test_user_token):
    # First get our own id
    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()

    response = client.put(
        f"/users/{me['id']}",
        json={"username": "updateduser"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updateduser"
    assert data["email"] == me["email"]
    assert data["role"] == me["role"]


def test_member_cannot_delete_another_user(client, member_target_token, admin_user):
    response = client.delete(
        f"/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {member_target_token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_admin_can_delete_user_without_magic_header(client, admin_user_token, delete_victim_user):
    response = client.delete(
        f"/users/{delete_victim_user.id}",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted"


def test_get_user_tasks_returns_only_owned_tasks(
    client,
    admin_user_token,
    test_user_token,
    member_target_token,
    member_target_user,
):
    client.post(
        "/tasks/",
        json={"title": "Owned by test user", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    target_task = client.post(
        "/tasks/",
        json={"title": "Owned by target user", "priority": 3, "status": "in_progress"},
        headers={"Authorization": f"Bearer {member_target_token}"},
    )
    assert target_task.status_code == 200

    response = client.get(
        f"/users/{member_target_user.id}/tasks",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Owned by target user"
    assert tasks[0]["owner_id"] == member_target_user.id
