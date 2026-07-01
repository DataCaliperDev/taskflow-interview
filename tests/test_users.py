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
    assert data["is_active"] is True
    assert "id" in data
    assert "password_hash" not in data


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(u["username"] == "testuser" for u in data)


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_user(client, test_user_token):
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
    assert response.json()["username"] == "updateduser"


def test_non_admin_cannot_delete_another_user(client, other_user_token, admin_user_token):
    admin_id = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    ).json()["id"]
    response = client.delete(
        f"/users/{admin_id}",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert response.status_code == 403


def test_magic_header_no_longer_grants_access(client, other_user_token, admin_user_token):
    admin_id = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    ).json()["id"]
    response = client.delete(
        f"/users/{admin_id}",
        headers={
            "Authorization": f"Bearer {other_user_token}",
            "X-Admin-Override": "admin-secret-2024",
        },
    )
    assert response.status_code == 403


def test_admin_can_delete_user(client, test_user_token, admin_user_token):
    target_id = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()["id"]
    response = client.delete(
        f"/users/{target_id}",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200
