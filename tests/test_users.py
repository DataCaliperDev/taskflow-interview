# tests/test_users.py

"""
Tests for the /users endpoints.
"""


def _assert_no_password_hash(payload):
    if isinstance(payload, list):
        for item in payload:
            assert "password_hash" not in item
    else:
        assert "password_hash" not in payload


def test_get_me(client, auth_headers):
    response = client.get(
        "/users/me",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert data["role"] == "member"
    assert "id" in data
    _assert_no_password_hash(data)


def test_list_users_authenticated(client, auth_headers):
    response = client.get(
        "/users/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(u["username"] == "testuser" for u in data)
    _assert_no_password_hash(data)


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_user(client, auth_headers):
    me = client.get(
        "/users/me",
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/users/{me['id']}",
        json={"username": "updateduser"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updateduser"
    assert data["email"] == me["email"]
    _assert_no_password_hash(data)


def test_member_cannot_delete_another_user(client, auth_headers, other_auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.delete(
        f"/users/{me['id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_admin_override_header_is_ignored(client, auth_headers, other_auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.delete(
        f"/users/{me['id']}",
        headers={**other_auth_headers, "X-Admin-Override": "admin-secret-2024"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_admin_can_delete_another_user(client, auth_headers, admin_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.delete(
        f"/users/{me['id']}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted"

    follow = client.get(f"/users/{me['id']}", headers=admin_headers)
    assert follow.status_code == 404
