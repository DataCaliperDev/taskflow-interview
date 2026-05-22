# tests/test_auth.py

"""Tests for the /auth endpoints."""

import hashlib

from app import models


def test_register_success(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password1",
    })
    assert response.status_code == 200


def test_register_duplicate_email(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "password1",
    })
    response = client.post("/auth/register", json={
        "username": "dupuser2",
        "email": "dup@example.com",
        "password": "password2",
    })
    assert response.status_code == 400


def test_register_response_omits_password_hash(client):
    """UC-2: registration response must not leak the hash."""
    response = client.post("/auth/register", json={
        "username": "noleak",
        "email": "noleak@example.com",
        "password": "password1",
    })
    assert response.status_code == 200
    assert "password_hash" not in response.json()


def test_stored_hash_is_bcrypt_not_plaintext(client, db_session):
    """UC-1: persisted hash is bcrypt, never the raw password or an MD5 of it."""
    password = "supersecret1"
    client.post("/auth/register", json={
        "username": "bcryptuser",
        "email": "bcrypt@example.com",
        "password": password,
    })
    user = db_session.query(models.User).filter_by(username="bcryptuser").one()
    assert user.password_hash != password
    assert user.password_hash != hashlib.md5(password.encode()).hexdigest()
    assert user.password_hash.startswith("$2")


def test_login_success(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "password1",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "password1",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "wrongpw",
        "email": "wrongpw@example.com",
        "password": "password1",
    })
    response = client.post("/auth/login", data={
        "username": "wrongpw",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_legacy_md5_login_rehashes_to_bcrypt(client, db_session):
    """UC-1: a user with a legacy MD5 hash logs in, then the row is upgraded to bcrypt."""
    legacy_password = "legacy1pw"
    legacy_user = models.User(
        username="legacy",
        email="legacy@example.com",
        password_hash=hashlib.md5(legacy_password.encode()).hexdigest(),
    )
    db_session.add(legacy_user)
    db_session.commit()

    response = client.post("/auth/login", data={
        "username": "legacy",
        "password": legacy_password,
    })
    assert response.status_code == 200

    db_session.refresh(legacy_user)
    assert legacy_user.password_hash.startswith("$2")
