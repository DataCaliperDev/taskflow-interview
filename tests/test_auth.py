"""Tests for the /auth endpoints."""


def test_register_returns_201_without_password_hash(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "strongpass123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert "password_hash" not in data
    assert "password" not in data


def test_register_duplicate_email(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "pass12345",
    })
    response = client.post("/auth/register", json={
        "username": "dupuser2",
        "email": "dup@example.com",
        "password": "pass45678",
    })
    assert response.status_code == 400


def test_register_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "sameuser",
        "email": "a@example.com",
        "password": "pass12345",
    })
    response = client.post("/auth/register", json={
        "username": "sameuser",
        "email": "b@example.com",
        "password": "pass12345",
    })
    assert response.status_code == 400


def test_register_missing_email(client):
    response = client.post("/auth/register", json={
        "username": "noemail",
        "password": "pass12345",
    })
    assert response.status_code == 422


def test_register_invalid_email(client):
    response = client.post("/auth/register", json={
        "username": "bademail",
        "email": "not-an-email",
        "password": "pass12345",
    })
    assert response.status_code == 422


def test_register_short_password(client):
    response = client.post("/auth/register", json={
        "username": "shortpw",
        "email": "shortpw@example.com",
        "password": "short",
    })
    assert response.status_code == 422


def test_login_success(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "mypassword123",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "mypassword123",
    })
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "loginuser2",
        "email": "login2@example.com",
        "password": "mypassword123",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser2",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_protected_route_without_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_password_is_hashed_not_plaintext(client, db_session):
    from app.models import User
    client.post("/auth/register", json={
        "username": "hashcheck",
        "email": "hash@example.com",
        "password": "plaintextpass123",
    })
    user = db_session.query(User).filter(User.username == "hashcheck").first()
    assert user.password_hash != "plaintextpass123"
    assert user.password_hash.startswith("$2")
