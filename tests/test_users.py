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
    # UC-2: /users/me must not leak the password hash.
    assert "password_hash" not in data


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    # UC-2: every user object returned by the list endpoint must be sanitised.
    # Asserting this on the list endpoint (in addition to /users/me and
    # /auth/register) demonstrates that the fix is schema-level, not
    # endpoint-by-endpoint.
    for user in response.json():
        assert "password_hash" not in user


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


# Issue: no test verifying that a normal user CANNOT update another user's profile
# Issue: no test for get_user_tasks


# ── UC-3: RBAC on DELETE /users/{id} ─────────────────────────────────────────
# These tests intentionally create throwaway "victim" users so they do not
# interfere with the long-lived testuser / other_user / admin_user fixtures
# that other tests in the module depend on.


def _register_victim(client, username: str) -> int:
    """Register a disposable user and return its id."""
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "victimpass",
        },
    )
    assert response.status_code == 200, response.text
    # /auth/register returns UserOut (UC-2 strips password_hash but keeps id).
    return response.json()["id"]


def test_non_admin_cannot_delete_another_user(client, other_user_token):
    victim_id = _register_victim(client, "victim_member")
    response = client.delete(
        f"/users/{victim_id}",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert response.status_code == 403


def test_magic_header_no_longer_grants_access(client, other_user_token):
    """Regression test: the old `X-Admin-Override: admin-secret-2024` bypass
    must not grant deletion rights anymore."""
    victim_id = _register_victim(client, "victim_magic")
    response = client.delete(
        f"/users/{victim_id}",
        headers={
            "Authorization": f"Bearer {other_user_token}",
            "X-Admin-Override": "admin-secret-2024",
        },
    )
    assert response.status_code == 403


def test_admin_can_delete_another_user(client, admin_token):
    victim_id = _register_victim(client, "victim_for_admin")
    response = client.delete(
        f"/users/{victim_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


def test_user_can_delete_self(client):
    """Self-deletion is still allowed even without admin role."""
    # Register a dedicated user so we don't kill any shared-fixture identity.
    client.post(
        "/auth/register",
        json={
            "username": "self_deleter",
            "email": "self_deleter@example.com",
            "password": "selfpass",
        },
    )
    login = client.post(
        "/auth/login",
        data={"username": "self_deleter", "password": "selfpass"},
    )
    token = login.json()["access_token"]

    me = client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    ).json()

    response = client.delete(
        f"/users/{me['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
