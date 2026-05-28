"""Tests for /auth (UC-12)."""


def test_register_returns_201_and_no_password_hash(client):
    resp = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "pw-min-8-chars",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "newuser"
    assert body["email"] == "new@example.com"
    assert body["role"] == "member"
    assert body["is_active"] is True
    assert "password_hash" not in body
    assert "password" not in body


def test_register_duplicate_email_rejected(client):
    client.post("/auth/register", json={
        "username": "dup1", "email": "dup@example.com", "password": "pw-1"})
    resp = client.post("/auth/register", json={
        "username": "dup2", "email": "dup@example.com", "password": "pw-2"})
    assert resp.status_code == 400
    assert "Email" in resp.json()["detail"]


def test_register_duplicate_username_rejected(client):
    client.post("/auth/register", json={
        "username": "twin", "email": "a@example.com", "password": "pw-1"})
    resp = client.post("/auth/register", json={
        "username": "twin", "email": "b@example.com", "password": "pw-2"})
    assert resp.status_code == 400
    assert "Username" in resp.json()["detail"]


def test_login_success(client, seeded_users):
    resp = client.post("/auth/login", data={"username": "bob", "password": "bob123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"].count(".") == 2


def test_login_wrong_password(client, seeded_users):
    resp = client.post("/auth/login", data={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", data={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    resp = client.get("/users/")
    assert resp.status_code == 401
