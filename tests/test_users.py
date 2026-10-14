# tests/test_users.py

"""
Tests for the /users endpoints.
"""


def test_get_me(client, user, user_headers):
    response = client.get("/users/me", headers=user_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["username"] == user.username
    assert data["email"] == user.email
    assert data["role"] == "member"
    assert data["is_active"] is True


def test_list_users_authenticated(client, user, other_user, user_headers):
    response = client.get("/users/", headers=user_headers)

    assert response.status_code == 200
    assert {u["username"] for u in response.json()} == {user.username, other_user.username}


def test_list_users_unauthenticated(client):
    response = client.get("/users/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_user(client, other_user, user_headers):
    response = client.get(f"/users/{other_user.id}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["username"] == other_user.username


def test_get_missing_user(client, user_headers):
    response = client.get("/users/9999", headers=user_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_update_user(client, user, user_headers):
    response = client.put(
        f"/users/{user.id}", json={"username": "updateduser"}, headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "updateduser"
    assert response.json()["email"] == user.email   # untouched field preserved


def test_get_user_tasks(client, user, user_headers, other_headers, make_task):
    mine = make_task(user_headers, title="mine")
    make_task(other_headers, title="theirs")

    response = client.get(f"/users/{user.id}/tasks", headers=user_headers)

    assert response.status_code == 200
    assert [t["id"] for t in response.json()] == [mine["id"]]
