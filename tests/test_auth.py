# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

import hashlib
from datetime import timedelta

import pytest
from jose import jwt

from app import models
from app.config import SECRET_KEY, ALGORITHM
from app.routers.auth import create_access_token, hash_password, verify_password

# Hardcoded names are safe again: the database is dropped and recreated for
# every test, so nothing survives to collide with.
PASSWORD = "correct-password"


def _register(client, username="newuser", **overrides):
    payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD,
    }
    payload.update(overrides)
    return client.post("/auth/register", json=payload)


def test_register(client, db_session):
    response = _register(client)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "newuser"
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "member"
    assert body["is_active"] is True

    stored = db_session.query(models.User).filter(
        models.User.username == "newuser"
    ).first()
    assert stored is not None
    assert stored.id == body["id"]


def test_register_duplicate_email(client):
    _register(client, "first")

    response = _register(client, "second", email="first@example.com")

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.xfail(
    reason="register only checks the email; a duplicate username reaches the "
           "database and raises IntegrityError. Adding the check belongs to the "
           "input-validation use case.",
    strict=True,
)
def test_register_duplicate_username(client):
    _register(client, "taken")

    response = _register(client, "taken", email="other@example.com")

    assert response.status_code == 400


@pytest.mark.parametrize("missing", ["username", "email", "password"])
def test_register_requires_every_field(client, missing):
    payload = {
        "username": "someone",
        "email": "someone@example.com",
        "password": PASSWORD,
    }
    del payload[missing]

    assert client.post("/auth/register", json=payload).status_code == 422


def test_login_success(client):
    user = _register(client, "loginuser").json()

    response = client.post("/auth/login", data={
        "username": "loginuser", "password": PASSWORD,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    # Decode rather than merely checking the key is present: a token that does
    # not carry the right subject would satisfy the old assertion.
    claims = jwt.decode(body["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert claims["sub"] == "loginuser"
    assert "exp" in claims
    assert user["id"]


def test_login_wrong_password(client):
    _register(client, "loginuser")

    response = client.post("/auth/login", data={
        "username": "loginuser", "password": "wrongpassword",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_unknown_user(client):
    response = client.post("/auth/login", data={
        "username": "nobody", "password": PASSWORD,
    })

    # Same message as a wrong password, so the response cannot be used to
    # enumerate which usernames exist.
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_an_inactive_user_cannot_use_their_token(client, db_session):
    user = _register(client, "suspended").json()
    token = client.post("/auth/login", data={
        "username": "suspended", "password": PASSWORD,
    }).json()["access_token"]

    row = db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first()
    row.is_active = False
    db_session.commit()

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_an_expired_token_is_rejected(client):
    _register(client, "expired")
    token = create_access_token(
        {"sub": "expired"}, expires_delta=timedelta(minutes=-1),
    )

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_a_token_for_a_deleted_user_is_rejected(client, db_session):
    """The subject is resolved against the database on every request, so a token
    outliving its account must stop working rather than fail open."""
    user = _register(client, "vanishing").json()
    token = client.post("/auth/login", data={
        "username": "vanishing", "password": PASSWORD,
    }).json()["access_token"]

    db_session.delete(db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first())
    db_session.commit()

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


# ── UC-1 · password hashing ──────────────────────────────────────────────────


def test_stored_hash_does_not_reveal_plaintext(client, db_session):
    """UC-1: a plaintext password cannot be recovered from the stored hash.

    Inspects the persisted row rather than the API response, so it holds
    whatever fields the response schema exposes.
    """
    password = "correct-horse-battery-staple"
    username = "hashcheck"

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
    username = "roundtrip"

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
    username = "rotate"

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
    username = "legacy"
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
    username = "corrupt"

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
