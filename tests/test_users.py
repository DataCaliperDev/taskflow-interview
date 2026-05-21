"""Tests for /users (UC-3, UC-6, UC-12)."""


def test_get_me_returns_no_password_hash(client, bob_token, auth_header):
    resp = client.get("/users/me", headers=auth_header(bob_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "bob"
    assert "password_hash" not in body


def test_list_users_unauthenticated_blocked(client):
    assert client.get("/users/").status_code == 401


def test_list_users_authenticated(client, bob_token, auth_header, seeded_users):
    resp = client.get("/users/", headers=auth_header(bob_token))
    assert resp.status_code == 200
    body = resp.json()
    usernames = {u["username"] for u in body}
    assert {"alice", "bob", "carol"} <= usernames
    for u in body:
        assert "password_hash" not in u


def test_self_can_update_own_profile(client, bob_token, auth_header, seeded_users):
    bob_id = seeded_users["bob"].id
    resp = client.put(
        f"/users/{bob_id}",
        json={"username": "bob_renamed"},
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "bob_renamed"


def test_member_cannot_update_other_user(client, bob_token, auth_header, seeded_users):
    """UC-3: members cannot mutate other users."""
    carol_id = seeded_users["carol"].id
    resp = client.put(
        f"/users/{carol_id}",
        json={"username": "hacked"},
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 403


def test_admin_can_update_any_user(client, admin_token, auth_header, seeded_users):
    carol_id = seeded_users["carol"].id
    resp = client.put(
        f"/users/{carol_id}",
        json={"email": "carol+new@example.com"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "carol+new@example.com"


def test_member_cannot_delete_user(client, bob_token, auth_header, seeded_users):
    """UC-3: X-Admin-Override is gone; only role-based admin may delete."""
    target = seeded_users["carol"].id
    resp = client.delete(f"/users/{target}", headers=auth_header(bob_token))
    assert resp.status_code == 403


def test_member_cannot_delete_self(client, bob_token, auth_header, seeded_users):
    """Self-delete is intentionally NOT allowed in this PR (admin-only)."""
    bob_id = seeded_users["bob"].id
    resp = client.delete(f"/users/{bob_id}", headers=auth_header(bob_token))
    assert resp.status_code == 403


def test_admin_can_delete_user(client, admin_token, auth_header, seeded_users):
    target = seeded_users["carol"].id
    resp = client.delete(f"/users/{target}", headers=auth_header(admin_token))
    assert resp.status_code == 204
    follow = client.get(f"/users/{target}", headers=auth_header(admin_token))
    assert follow.status_code == 404


def test_admin_override_header_no_longer_grants_access(
    client, bob_token, auth_header, seeded_users
):
    """UC-3: legacy magic header must not bypass role check."""
    target = seeded_users["carol"].id
    headers = auth_header(bob_token) | {"X-Admin-Override": "admin-secret-2024"}
    resp = client.delete(f"/users/{target}", headers=headers)
    assert resp.status_code == 403


def test_get_user_tasks_paginated(
    client, bob_token, auth_header, make_task, seeded_users
):
    """UC-6: paginated user tasks."""
    for i in range(12):
        make_task(bob_token, title=f"t{i}")
    bob_id = seeded_users["bob"].id
    resp = client.get(
        f"/users/{bob_id}/tasks?page=1&page_size=5",
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 12
    assert body["page_size"] == 5
    assert body["total_pages"] == 3
    assert len(body["items"]) == 5


def test_get_user_tasks_unknown_user(client, bob_token, auth_header):
    resp = client.get("/users/9999/tasks", headers=auth_header(bob_token))
    assert resp.status_code == 404
