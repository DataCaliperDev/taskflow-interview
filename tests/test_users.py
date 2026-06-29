"""Tests for the /users endpoints."""


def test_get_me_omits_password_hash(client, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "password_hash" not in data


def test_list_users_omits_password_hash(client, auth_headers):
    response = client.get("/users/", headers=auth_headers)
    assert response.status_code == 200
    for user in response.json():
        assert "password_hash" not in user


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401
    assert response.json()["detail"]


def test_update_own_user_applies_change(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    response = client.put(
        f"/users/{me['id']}",
        json={"username": "updateduser"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["username"] == "updateduser"


def test_cannot_update_other_user(client, auth_headers):
    client.post("/auth/register", json={
        "username": "victim",
        "email": "victim@example.com",
        "password": "victim12345",
    })
    victim = client.get("/users/", headers=auth_headers).json()
    victim_id = next(u["id"] for u in victim if u["username"] == "victim")

    response = client.put(
        f"/users/{victim_id}",
        json={"username": "hacked"},
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_non_admin_cannot_delete_other_user(client, auth_headers):
    client.post("/auth/register", json={
        "username": "target",
        "email": "target@example.com",
        "password": "target12345",
    })
    users = client.get("/users/", headers=auth_headers).json()
    target_id = next(u["id"] for u in users if u["username"] == "target")

    response = client.delete(f"/users/{target_id}", headers=auth_headers)
    assert response.status_code == 403


def test_admin_can_delete_user(client, admin_token):
    client.post("/auth/register", json={
        "username": "deleteme",
        "email": "deleteme@example.com",
        "password": "deleteme123",
    })
    headers = {"Authorization": f"Bearer {admin_token}"}
    users = client.get("/users/", headers=headers).json()
    target_id = next(u["id"] for u in users if u["username"] == "deleteme")

    response = client.delete(f"/users/{target_id}", headers=headers)
    assert response.status_code == 204


def test_get_user_tasks_paginated(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    client.post("/tasks/", json={"title": "Mine"}, headers=auth_headers)
    response = client.get(f"/users/{me['id']}/tasks", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Mine"
