# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

import hashlib

from app import models
from app.routers.auth import hash_password, verify_password
from tests.conftest import TestingSessionLocal


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
    assert data["is_active"] is True
    assert "id" in data
    assert "password_hash" not in data


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


def test_register_missing_field(client):
    response = client.post("/auth/register", json={
        "username": "nofield",
        "password": "pass123",
        # missing email
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
    assert "access_token" in data
    assert data["token_type"] == "bearer"
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


def test_legacy_md5_user_can_login_and_hash_is_upgraded(client):
    # Simulate a pre-migration user whose password_hash is an MD5 digest.
    # Login must succeed (not 500, not 401) and the stored hash must be
    # silently upgraded to bcrypt so the next login uses the normal path.
    client.post("/auth/register", json={
        "username": "legacyuser",
        "email": "legacy@example.com",
        "password": "password123",
    })
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "legacyuser").first()
        user.password_hash = hashlib.md5("password123".encode()).hexdigest()
        db.commit()
    finally:
        db.close()

    # First login: MD5 path — should succeed and trigger re-hash
    response = client.post("/auth/login", data={
        "username": "legacyuser",
        "password": "password123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Verify the hash was upgraded to bcrypt in the DB
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "legacyuser").first()
        assert user.password_hash.startswith("$2b$")
    finally:
        db.close()

    # Second login: now goes through normal bcrypt path
    response = client.post("/auth/login", data={
        "username": "legacyuser",
        "password": "password123",
    })
    assert response.status_code == 200


def test_legacy_md5_user_wrong_password_returns_401(client):
    # Wrong password against an MD5 hash must return 401, not 500.
    client.post("/auth/register", json={
        "username": "legacyuser2",
        "email": "legacy2@example.com",
        "password": "password123",
    })
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "legacyuser2").first()
        user.password_hash = hashlib.md5("password123".encode()).hexdigest()
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/login", data={
        "username": "legacyuser2",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_password_hash_is_not_plaintext():
    password = "secret"
    hashed = hash_password(password)

    assert hashed != password
    assert password not in hashed
    md5_digest = hashlib.md5(password.encode()).hexdigest()
    assert hashed != md5_digest


def test_password_hash_is_not_recoverable():
    password = "hunter2"
    hash_a = hash_password(password)
    hash_b = hash_password(password)

    # bcrypt salting: same password yields different hashes each time
    assert hash_a != hash_b

    # verify_password must accept the correct plaintext against either hash
    assert verify_password(password, hash_a) is True
    assert verify_password(password, hash_b) is True

    # and reject a wrong password
    assert verify_password("wrongpassword", hash_a) is False
