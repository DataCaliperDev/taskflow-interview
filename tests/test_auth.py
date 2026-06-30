# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

import hashlib

from app.routers.auth import hash_password, verify_password


def test_register(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "pass",   # Issue: tests should not use trivially weak passwords — masks validation gaps
    })
    assert response.status_code == 200
    # Issue: response includes password_hash — test doesn't assert this field is absent


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
    assert "access_token" in response.json()
    # Issue: doesn't assert token_type == "bearer"
    # Issue: doesn't verify the token is actually a valid JWT


def test_login_wrong_password(client):
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


# Issue: no test for accessing a protected route without a token
# Issue: no test for accessing a protected route with an expired token
# Issue: no test for registering with a missing field (e.g., no email)
# Issue: no test for duplicate username registration


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
