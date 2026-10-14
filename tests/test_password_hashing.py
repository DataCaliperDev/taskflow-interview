# tests/test_password_hashing.py

"""
Tests for password storage (UC-1): bcrypt via passlib, legacy MD5 upgrade.
"""

import hashlib

from app import models
from app.routers.auth import hash_password, verify_password


def _stored_hash(db, username: str) -> str:
    db.expire_all()  # re-read what the API committed
    return db.query(models.User).filter_by(username=username).one().password_hash


def test_hash_is_bcrypt_and_does_not_reveal_plaintext():
    password = "correct-horse-battery"
    hashed = hash_password(password)

    assert hashed.startswith("$2b$")                       # bcrypt identifier
    assert password not in hashed
    assert hashed != hashlib.md5(password.encode()).hexdigest()


def test_hash_is_salted():
    # Same input, different hashes: precomputed (rainbow) tables are useless
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_password():
    hashed = hash_password("s3cret-pass")

    assert verify_password("s3cret-pass", hashed) is True
    assert verify_password("wrong-pass", hashed) is False


def test_registered_password_is_stored_as_bcrypt(client, db_session):
    client.post("/auth/register", json={
        "username": "hashcheck",
        "email": "hashcheck@example.com",
        "password": "plaintext-pw",
    })

    stored = _stored_hash(db_session, "hashcheck")
    assert stored.startswith("$2b$")
    assert "plaintext-pw" not in stored
    assert stored != hashlib.md5(b"plaintext-pw").hexdigest()


def test_legacy_md5_hash_is_upgraded_on_login(client, db_session):
    db_session.add(models.User(
        username="legacyuser",
        email="legacy@example.com",
        password_hash=hashlib.md5(b"legacy-pass").hexdigest(),
    ))
    db_session.commit()

    response = client.post("/auth/login", data={
        "username": "legacyuser", "password": "legacy-pass",
    })

    assert response.status_code == 200
    assert _stored_hash(db_session, "legacyuser").startswith("$2b$")
    # And the upgraded hash still works
    assert client.post("/auth/login", data={
        "username": "legacyuser", "password": "legacy-pass",
    }).status_code == 200
