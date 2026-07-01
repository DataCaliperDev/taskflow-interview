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
    assert "username" in data
    assert "password_hash" not in data


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    # Issue: test expects 401, which is correct — but it only checks the code, not the error message
    assert response.status_code == 401


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
    # Issue: no assertion that username was actually changed to "updateduser"


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


def test_admin_can_delete_user(client, admin_user_token):
    client.post("/auth/register", json={
        "username": "throwaway",
        "email": "throwaway@example.com",
        "password": "throwaway",
    })
    token = client.post(
        "/auth/login",
        data={"username": "throwaway", "password": "throwaway"},
    ).json()["access_token"]
    throwaway_id = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    response = client.delete(
        f"/users/{throwaway_id}",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    )
    assert response.status_code == 200


# Issue: no test verifying that a normal user CANNOT update another user's profile
# Issue: no test for get_user_tasks
