# tests/test_authorization.py

"""
UC-3: ownership and role-based access control.

Members may modify only their own tasks / account; admins may modify any.
"""

FORBIDDEN = "Not authorized to modify this resource"


# ── Task update ───────────────────────────────────────────────────────────────

def test_owner_can_update_own_task(client, user_headers, task):
    response = client.put(f"/tasks/{task['id']}", json={"title": "Mine"}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["title"] == "Mine"


def test_member_cannot_update_others_task(client, user_headers, other_headers, task):
    response = client.put(f"/tasks/{task['id']}", json={"title": "Hijacked"}, headers=other_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == FORBIDDEN
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).json()["title"] == task["title"]


def test_admin_can_update_any_task(client, admin_headers, task, user):
    response = client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["owner_id"] == user.id   # ownership is not transferred


def test_update_missing_task_is_404(client, admin_headers):
    response = client.put("/tasks/9999", json={"title": "x"}, headers=admin_headers)

    assert response.status_code == 404


# ── Task delete ───────────────────────────────────────────────────────────────

def test_owner_can_delete_own_task(client, user_headers, task):
    response = client.delete(f"/tasks/{task['id']}", headers=user_headers)

    assert response.status_code == 200
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).status_code == 404


def test_member_cannot_delete_others_task(client, user_headers, other_headers, task):
    response = client.delete(f"/tasks/{task['id']}", headers=other_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == FORBIDDEN
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).status_code == 200


def test_admin_can_delete_any_task(client, admin_headers, user_headers, task):
    response = client.delete(f"/tasks/{task['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).status_code == 404


# ── User delete (replaces the X-Admin-Override header) ───────────────────────

def test_member_cannot_delete_another_user(client, other_user, user_headers, admin_headers):
    response = client.delete(f"/users/{other_user.id}", headers=user_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == FORBIDDEN
    assert client.get(f"/users/{other_user.id}", headers=admin_headers).status_code == 200


def test_magic_admin_header_no_longer_grants_access(client, other_user, user_headers, admin_headers):
    response = client.delete(
        f"/users/{other_user.id}",
        headers={**user_headers, "X-Admin-Override": "admin-secret-2024"},
    )

    assert response.status_code == 403
    assert client.get(f"/users/{other_user.id}", headers=admin_headers).status_code == 200


def test_member_can_delete_own_account(client, user, user_headers, admin_headers):
    response = client.delete(f"/users/{user.id}", headers=user_headers)

    assert response.status_code == 200
    assert response.json() == {"message": "User deleted"}
    assert client.get(f"/users/{user.id}", headers=admin_headers).status_code == 404


def test_admin_can_delete_another_user(client, other_user, admin_headers):
    response = client.delete(f"/users/{other_user.id}", headers=admin_headers)

    assert response.status_code == 200
    assert client.get(f"/users/{other_user.id}", headers=admin_headers).status_code == 404


def test_admin_delete_missing_user_is_404(client, admin_headers):
    response = client.delete("/users/9999", headers=admin_headers)

    assert response.status_code == 404


# ── User update (same rule, applied consistently) ────────────────────────────

def test_member_cannot_update_another_user(client, other_user, user_headers):
    response = client.put(
        f"/users/{other_user.id}", json={"username": "pwned"}, headers=user_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == FORBIDDEN


def test_admin_can_update_another_user(client, other_user, admin_headers):
    response = client.put(
        f"/users/{other_user.id}", json={"username": "renamed"}, headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "renamed"
