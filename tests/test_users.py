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
