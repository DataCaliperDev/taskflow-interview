# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

from app.routers.auth import hash_password, verify_password


def test_password_hash_is_not_plaintext_and_verifies():
    plain_password = "super-secret-password-123"
    hashed_password = hash_password(plain_password)

    assert hashed_password != plain_password
    assert hashed_password.startswith("$2")
    assert verify_password(plain_password, hashed_password)
    assert not verify_password("wrong-password", hashed_password)


def test_register(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "pass12345",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["is_active"] is True
    assert data["role"] == "member"
    assert "password_hash" not in data


def test_register_duplicate_email(client):
    client.post(
        "/auth/register",
        json={
            "username": "dupuser",
            "email": "dup@example.com",
            "password": "pass12345",
        },
    )
    response = client.post(
        "/auth/register",
        json={
            "username": "dupuser2",
            "email": "dup@example.com",
            "password": "pass45678",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_success(client):
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "mypassword",
        },
    )
    response = client.post(
        "/auth/login",
        data={
            "username": "loginuser",
            "password": "mypassword",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 10


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={
            "username": "wrongpassuser",
            "email": "wrongpass@example.com",
            "password": "mypassword",
        },
    )
    response = client.post(
        "/auth/login",
        data={
            "username": "wrongpassuser",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_protected_route_requires_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
