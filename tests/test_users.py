# tests/test_users.py

"""
Tests for the /users endpoints.
"""


def test_get_me(client, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert data["role"] == "member"


def test_list_users_authenticated(client, auth_headers):
    response = client.get("/users/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(u["username"] == "testuser" for u in data)


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401


def test_update_user(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()

    response = client.put(
        f"/users/{me['id']}",
        json={"username": "updateduser"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == me["id"]
    assert data["username"] == "updateduser"
    assert data["email"] == me["email"]


# ── New tests (UC-12) ─────────────────────────────────────────────────────────

def test_get_user_by_id(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.get(f"/users/{me['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == me["id"]


def test_get_user_tasks(client, auth_headers, created_task):
    owner_id = created_task["owner_id"]
    response = client.get(f"/users/{owner_id}/tasks", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(t["id"] == created_task["id"] for t in data)


# ── UC-3: User authorization ──────────────────────────────────────────────────

def test_user_can_delete_self(client, auth_headers):
    """A user deletes their own account (self) → 200."""
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.delete(f"/users/{me['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted"


def test_non_admin_cannot_delete_other_user(
    client, auth_headers, second_auth_headers
):
    """A non-admin deleting another user's account → 403."""
    target = client.get("/users/me", headers=auth_headers).json()
    response = client.delete(
        f"/users/{target['id']}", headers=second_auth_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"


def test_admin_can_delete_other_user(
    client, auth_headers, admin_auth_headers
):
    """An admin deletes another user → 200."""
    target = client.get("/users/me", headers=auth_headers).json()
    response = client.delete(
        f"/users/{target['id']}", headers=admin_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted"


def test_admin_override_header_no_longer_grants_delete(
    client, auth_headers, second_auth_headers
):
    """The old X-Admin-Override magic header must NOT let a non-admin delete."""
    target = client.get("/users/me", headers=auth_headers).json()
    headers = dict(second_auth_headers)
    headers["X-Admin-Override"] = "admin-secret-2024"
    response = client.delete(f"/users/{target['id']}", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"
    # The targeted user still exists.
    follow = client.get(f"/users/{target['id']}", headers=auth_headers)
    assert follow.status_code == 200


# ── UC-3 (extension): update_user ownership gate ─────────────────────────────

def test_non_admin_cannot_update_other_user(
    client, auth_headers, second_auth_headers
):
    """(Extension) A non-admin updating another user's profile → 403."""
    target = client.get("/users/me", headers=auth_headers).json()
    response = client.put(
        f"/users/{target['id']}",
        json={"username": "hacked"},
        headers=second_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"
    # Profile unchanged.
    after = client.get("/users/me", headers=auth_headers).json()
    assert after["username"] == target["username"]


def test_update_user_authorizes_before_lookup(
    client, auth_headers, second_auth_headers
):
    """(Extension) update_user authorizes before the DB lookup (403-before-404).

    A non-admin updating another user's id → 403, and updating a clearly
    non-existent id also → 403 (not 404), proving the id-enumeration leak is
    closed: authorization runs before the existence check.
    """
    target = client.get("/users/me", headers=auth_headers).json()

    # Existing other user's id → 403 (not their own).
    response = client.put(
        f"/users/{target['id']}",
        json={"username": "hacked"},
        headers=second_auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"

    # Clearly non-existent id → still 403 (no 404 leak about id existence).
    missing = client.put(
        "/users/999999",
        json={"username": "hacked"},
        headers=second_auth_headers,
    )
    assert missing.status_code == 403
    assert missing.json()["detail"] == "Not authorized"


def test_owner_can_update_own_profile(client, auth_headers):
    """The owner updating their own profile → 200."""
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.put(
        f"/users/{me['id']}",
        json={"username": "renamed"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["username"] == "renamed"


def test_admin_can_update_other_user_profile(
    client, auth_headers, admin_auth_headers
):
    """(Extension) An admin updating another user's profile → 200."""
    target = client.get("/users/me", headers=auth_headers).json()
    response = client.put(
        f"/users/{target['id']}",
        json={"username": "adminedited"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["username"] == "adminedited"
