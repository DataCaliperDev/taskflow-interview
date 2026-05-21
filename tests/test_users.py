# tests/test_users.py

"""
Tests for the /users endpoints.
"""

import pytest
from tests.conftest import TestingSessionLocal
from app import models


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(client, username, email, password="Password123"):
    r = client.post("/auth/register", json={
        "username": username, "email": email, "password": password,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _token(client, username, password="Password123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(user_id: int):
    """Directly set role=admin in the test DB (register API always creates member)."""
    db = TestingSessionLocal()
    try:
        db.query(models.User).filter(models.User.id == user_id).update({"role": "admin"})
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Authorization fixture — 1 admin + 2 members, created once per module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def auth_users(client):
    """
    Returns a dict with tokens and IDs for:
      - admin_user
      - member_a
      - member_b
    """
    admin_data   = _register(client, "auth_admin",    "auth_admin@example.com")
    member_a_data = _register(client, "auth_member_a", "auth_member_a@example.com")
    member_b_data = _register(client, "auth_member_b", "auth_member_b@example.com")

    _promote_to_admin(admin_data["id"])

    return {
        "admin":    {"id": admin_data["id"],    "token": _token(client, "auth_admin")},
        "member_a": {"id": member_a_data["id"], "token": _token(client, "auth_member_a")},
        "member_b": {"id": member_b_data["id"], "token": _token(client, "auth_member_b")},
    }


# ---------------------------------------------------------------------------
# Authorization test cases
# ---------------------------------------------------------------------------

def test_admin_can_update_member_profile(client, auth_users):
    """Admin can update any member's profile."""
    # Use a disposable target so member_a's username (stored in JWT sub) stays intact
    target = _register(client, "admin_update_target", "admin_update_target@example.com")
    response = client.put(
        f"/users/{target['id']}",
        json={"email": "admin_update_target_new@example.com"},
        headers=_headers(auth_users["admin"]["token"]),
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin_update_target_new@example.com"


def test_member_can_update_own_profile(client, auth_users):
    """Member can update their own profile."""
    # Change email, not username — username is the JWT sub claim and must stay stable
    response = client.put(
        f"/users/{auth_users['member_b']['id']}",
        json={"email": "auth_member_b_new@example.com"},
        headers=_headers(auth_users["member_b"]["token"]),
    )
    assert response.status_code == 200
    assert response.json()["email"] == "auth_member_b_new@example.com"


def test_member_cannot_update_other_member_profile(client, auth_users):
    """Member A cannot update Member B's profile."""
    response = client.put(
        f"/users/{auth_users['member_b']['id']}",
        json={"username": "should_not_change"},
        headers=_headers(auth_users["member_a"]["token"]),
    )
    assert response.status_code == 403


def test_member_cannot_delete_itself(client, auth_users):
    """Member cannot delete their own account."""
    response = client.delete(
        f"/users/{auth_users['member_a']['id']}",
        headers=_headers(auth_users["member_a"]["token"]),
    )
    assert response.status_code == 403


def test_member_cannot_delete_other_member(client, auth_users):
    """Member A cannot delete Member B."""
    response = client.delete(
        f"/users/{auth_users['member_b']['id']}",
        headers=_headers(auth_users["member_a"]["token"]),
    )
    assert response.status_code == 403


def test_admin_can_delete_member(client, auth_users):
    """Admin can delete a member account."""
    # Register a disposable user so we don't break other tests
    disposable = _register(client, "disposable_user", "disposable@example.com")
    response = client.delete(
        f"/users/{disposable['id']}",
        headers=_headers(auth_users["admin"]["token"]),
    )
    assert response.status_code == 200


def test_get_me(client, test_user_token):
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    # Issue: does not assert that password_hash is NOT in the response


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ---------------------------------------------------------------------------
# Unauthorized access — no token / invalid token
# ---------------------------------------------------------------------------

def test_get_me_no_token(client):
    """GET /users/me without a token must return 401."""
    response = client.get("/users/me")
    assert response.status_code == 401


def test_get_user_no_token(client, test_user_token):
    """GET /users/{id} without a token must return 401."""
    me = client.get("/users/me", headers={"Authorization": f"Bearer {test_user_token}"}).json()
    response = client.get(f"/users/{me['id']}")
    assert response.status_code == 401


def test_update_user_no_token(client, test_user_token):
    """PUT /users/{id} without a token must return 401."""
    me = client.get("/users/me", headers={"Authorization": f"Bearer {test_user_token}"}).json()
    response = client.put(f"/users/{me['id']}", json={"email": "x@x.com"})
    assert response.status_code == 401


def test_delete_user_no_token(client, test_user_token):
    """DELETE /users/{id} without a token must return 401."""
    me = client.get("/users/me", headers={"Authorization": f"Bearer {test_user_token}"}).json()
    response = client.delete(f"/users/{me['id']}")
    assert response.status_code == 401


def test_endpoints_reject_invalid_token(client):
    """All protected /users endpoints must return 401 for a malformed token."""
    bad_headers = {"Authorization": "Bearer this.is.not.a.valid.jwt"}
    assert client.get("/users/",    headers=bad_headers).status_code == 401
    assert client.get("/users/me",  headers=bad_headers).status_code == 401
    assert client.get("/users/1",   headers=bad_headers).status_code == 401
    assert client.put("/users/1",   headers=bad_headers, json={}).status_code == 401
    assert client.delete("/users/1",headers=bad_headers).status_code == 401


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
# Issue: no test for the admin override header on DELETE
# Issue: no test for get_user_tasks
