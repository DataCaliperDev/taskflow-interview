# tests/test_users.py

"""
Tests for the /users endpoints.
"""


def test_get_me_returns_full_profile(client, test_user_token):
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # UC-12: assert every public field on the user profile.
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert data["is_active"] is True
    assert data["role"] == "member"
    assert isinstance(data["id"], int)
    assert "created_at" in data
    # UC-2: /users/me must not leak the password hash.
    assert "password_hash" not in data


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    # The caller themselves must be in the list.
    usernames = [u["username"] for u in payload]
    assert "testuser" in usernames
    # UC-2: every user object returned by the list endpoint must be sanitised.
    # Asserting this on the list endpoint (in addition to /users/me and
    # /auth/register) demonstrates that the fix is schema-level, not
    # endpoint-by-endpoint.
    for user in payload:
        assert "password_hash" not in user


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401


def test_update_user_persists_the_change(client, test_user_token):
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
    # UC-12: verify the update actually applied — both in the PUT response…
    assert response.json()["username"] == "updateduser"
    # Session-stability requirement:
    # existing token must remain valid after username change.
    fresh = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    assert fresh["username"] == "updateduser"


def test_username_change_does_not_break_existing_session(client, test_user_token):
    """Regression test: old token should keep working after username update."""
    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()

    update = client.put(
        f"/users/{me['id']}",
        json={"username": "stable_session_user"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert update.status_code == 200

    # Use the same pre-update token on a different protected endpoint too.
    users = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert users.status_code == 200


def test_admin_update_invalidates_target_user_session(client, admin_token):
    """If admin updates another member's info, target's existing token is revoked."""
    # Create an independent member account to avoid fixture-order ambiguity.
    register = client.post(
        "/auth/register",
        json={
            "username": "target_member",
            "email": "target_member@example.com",
            "password": "targetpass",
        },
    )
    assert register.status_code == 200
    target_user_id = register.json()["id"]

    target_login = client.post(
        "/auth/login",
        data={"username": "target_member", "password": "targetpass"},
    )
    assert target_login.status_code == 200
    target_old_token = target_login.json()["access_token"]

    # Admin updates target user's profile.
    update = client.put(
        f"/users/{target_user_id}",
        json={"email": "other-updated@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update.status_code == 200
    assert update.json()["email"] == "other-updated@example.com"

    # Target user's old token should now be rejected.
    old_token_me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {target_old_token}"},
    )
    assert old_token_me.status_code == 401

    # Target user can re-login and get a fresh working token.
    relogin = client.post(
        "/auth/login",
        data={"username": "target_member", "password": "targetpass"},
    )
    assert relogin.status_code == 200
    new_token = relogin.json()["access_token"]
    new_token_me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert new_token_me.status_code == 200


# ── UC-12 · New coverage on /users endpoints ────────────────────────────────


def test_get_user_by_id_returns_public_profile(client, test_user_token):
    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()
    response = client.get(
        f"/users/{me['id']}",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == me["id"]
    assert body["username"] == me["username"]
    assert "password_hash" not in body


def test_get_user_tasks_returns_only_owned_tasks(
    client, test_user_token, other_user_token
):
    """`GET /users/{id}/tasks` must return only tasks owned by that user."""
    # testuser owns two tasks
    for title in ["mine A", "mine B"]:
        client.post(
            "/tasks/",
            json={"title": title, "priority": 2, "status": "todo"},
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
    # other_user owns one task
    client.post(
        "/tasks/",
        json={"title": "not mine", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {other_user_token}"},
    )

    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()

    response = client.get(
        f"/users/{me['id']}/tasks",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    titles = [t["title"] for t in payload]
    assert sorted(titles) == ["mine A", "mine B"]
    # Every returned task must belong to testuser.
    for task in payload:
        assert task["owner_id"] == me["id"]


def test_get_nonexistent_user_returns_404(client, test_user_token):
    response = client.get(
        "/users/999999",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 404


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
