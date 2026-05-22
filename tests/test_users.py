# tests/test_users.py

"""Tests for the /users endpoints."""


def test_me_response_omits_password_hash(authed_client):
    """UC-2: /users/me must not leak the hash."""
    response = authed_client.get("/users/me")
    assert response.status_code == 200
    assert "password_hash" not in response.json()


def test_list_users_response_omits_password_hash(authed_client):
    """UC-2: /users/ must not leak any user's hash."""
    response = authed_client.get("/users/")
    assert response.status_code == 200
    for user in response.json():
        assert "password_hash" not in user


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    assert response.status_code == 401


def test_register_rejects_invalid_email(client):
    """UC-9: EmailStr rejects malformed emails."""
    response = client.post("/auth/register", json={
        "username": "bademail",
        "email": "not-an-email",
        "password": "password1",
    })
    assert response.status_code == 422


def test_register_rejects_short_password(client):
    """UC-9: password must be >= 8 chars."""
    response = client.post("/auth/register", json={
        "username": "shortpw",
        "email": "shortpw@example.com",
        "password": "short",
    })
    assert response.status_code == 422


def test_register_rejects_short_username(client):
    """UC-9: username must be >= 3 chars."""
    response = client.post("/auth/register", json={
        "username": "a",
        "email": "shortuser@example.com",
        "password": "password1",
    })
    assert response.status_code == 422
