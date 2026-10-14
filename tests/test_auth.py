# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

import hashlib

from app.models import User


def test_register(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "pass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["role"] == "member"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "password_hash" not in data
    assert "password" not in data


def test_register_duplicate_email(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "pass123",
    })
    response = client.post("/auth/register", json={
        "username": "dupuser2",
        "email": "dup@example.com",
        "password": "pass456",
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_missing_email(client):
    response = client.post("/auth/register", json={
        "username": "noemail",
        "password": "pass123",
    })
    assert response.status_code == 422


def test_login_success(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "mypassword",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "mypassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "mypassword",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_unknown_user(client):
    response = client.post("/auth/login", data={
        "username": "ghost",
        "password": "whatever",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_password_not_stored_in_plaintext(client, db):
    password = "supersecret123"
    response = client.post("/auth/register", json={
        "username": "hashuser",
        "email": "hash@example.com",
        "password": password,
    })
    assert response.status_code == 200
    assert "password_hash" not in response.json()

    user = db.query(User).filter(User.username == "hashuser").first()
    stored = user.password_hash

    assert stored != password
    assert stored != hashlib.md5(password.encode()).hexdigest()
    assert password not in stored
    assert stored.startswith("$2")
