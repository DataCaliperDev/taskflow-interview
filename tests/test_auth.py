# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

import hashlib
import uuid

from app import models
from app.routers.auth import hash_password, verify_password


def _unique(prefix: str) -> str:
    """Unique-per-run identifier.

    username/email are UNIQUE and the suite reuses an on-disk test.db between
    runs, so hardcoded names collide on a rerun. (Resetting the DB per test is
    UC-12's scope.)
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_register(client):
    # Names are generated per run: the suite keeps an on-disk test.db that is
    # never reset, so a hardcoded email is already taken on the second run and
    # register answers 400. Proper per-test teardown is UC-12's scope.
    username = _unique("newuser")
    response = client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
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


# ── UC-1 · password hashing ──────────────────────────────────────────────────


def test_stored_hash_does_not_reveal_plaintext(client, db_session):
    """UC-1: a plaintext password cannot be recovered from the stored hash.

    Inspects the persisted row rather than the API response, so it holds
    whatever fields the response schema exposes.
    """
    password = "correct-horse-battery-staple"
    username = _unique("hashcheck")

    response = client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
    })
    assert response.status_code == 200

    stored = db_session.query(models.User).filter(
        models.User.username == username
    ).first().password_hash

    # The password must be neither the stored value nor embedded anywhere in it.
    assert stored != password
    assert password not in stored

    # Decisive: exactly what the old code would have written, so this fails on
    # the MD5 path and passes on bcrypt — it proves the algorithm changed, not
    # just that the hash looks unlike the password.
    assert stored != hashlib.md5(password.encode()).hexdigest()

    assert stored.startswith("$2b$")   # bcrypt's modular-crypt prefix


def test_hashing_is_salted(client):
    """One password, two hashes — the property the unsalted MD5 lacked.

    Both must still verify, which is why verification cannot be "hash the input
    and compare strings".
    """
    password = "same-password-twice"

    first = hash_password(password)
    second = hash_password(password)

    assert first != second
    assert verify_password(password, first)
    assert verify_password(password, second)
    assert not verify_password("not-the-password", first)


def test_register_then_login_round_trip(client):
    """No regression: an account created under bcrypt can log back in.

    Goes through HTTP rather than the helpers on purpose — a salt bug only
    surfaces when hashing and verification are separate round trips.
    verify_password(pw, hash_password(pw)) would pass even with a stored hash
    that login could never use.
    """
    password = "round-trip-pass"
    username = _unique("roundtrip")

    register = client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
    })
    assert register.status_code == 200

    login = client.post("/auth/login", data={
        "username": username,
        "password": password,
    })
    assert login.status_code == 200

    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_password_change_invalidates_the_old_password(client):
    """Covers the second hashing call site, PUT /users/{id}.

    users.py imports hash_password from here, so it picks up bcrypt for free —
    worth asserting rather than assuming.
    """
    old_password = "original-password"
    new_password = "rotated-password"
    username = _unique("rotate")

    register = client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": old_password,
    })
    user_id = register.json()["id"]

    token = client.post("/auth/login", data={
        "username": username,
        "password": old_password,
    }).json()["access_token"]

    updated = client.put(
        f"/users/{user_id}",
        json={"password": new_password},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200

    assert client.post("/auth/login", data={
        "username": username,
        "password": new_password,
    }).status_code == 200

    assert client.post("/auth/login", data={
        "username": username,
        "password": old_password,
    }).status_code == 401


def test_legacy_md5_account_logs_in_and_is_upgraded(client, db_session):
    """Lazy migration: pre-existing MD5 rows keep working and self-heal.

    Not hypothetical — taskflow.db ships in the repo with MD5 digests. Without
    the deprecated-scheme fallback passlib raises UnknownHashError and login
    answers 500.
    """
    password = "legacy-account-pw"
    username = _unique("legacy")
    legacy_digest = hashlib.md5(password.encode()).hexdigest()

    db_session.add(models.User(
        username=username,
        email=f"{username}@example.com",
        password_hash=legacy_digest,
        role="member",
    ))
    db_session.commit()

    login = client.post("/auth/login", data={
        "username": username,
        "password": password,
    })
    assert login.status_code == 200

    # The successful login should have rewritten the digest in place.
    db_session.expire_all()   # drop the cached row so we read what login wrote
    stored = db_session.query(models.User).filter(
        models.User.username == username
    ).first().password_hash

    assert stored.startswith("$2b$")
    assert stored != legacy_digest

    # And the same password still works against the upgraded hash.
    assert client.post("/auth/login", data={
        "username": username,
        "password": password,
    }).status_code == 200


def test_unreadable_password_hash_is_rejected_with_401(client, db_session):
    """A corrupt hash is a failed login, not a server error.

    password_hash has no NOT NULL constraint and no format validation, so an
    unparseable value is reachable; passlib raises on those.
    """
    username = _unique("corrupt")

    db_session.add(models.User(
        username=username,
        email=f"{username}@example.com",
        password_hash="not-a-valid-hash",
        role="member",
    ))
    db_session.commit()

    response = client.post("/auth/login", data={
        "username": username,
        "password": "any-password",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
