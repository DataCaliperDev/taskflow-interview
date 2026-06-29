# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""


def test_register(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "newpass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["is_active"] is True
    assert data["role"] == "member"


def test_register_duplicate_email(client):
    first = client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "duppass123",
    })
    assert first.status_code == 200

    response = client.post("/auth/register", json={
        "username": "dupuser2",
        "email": "dup@example.com",
        "password": "duppass456",
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_success(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "mypassword1",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "mypassword1",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert data["access_token"]


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "mypassword1",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


# ── New tests (UC-12) ─────────────────────────────────────────────────────────

def test_login_nonexistent_user(client):
    """Logging in as an unknown user is rejected with 401."""
    response = client.post("/auth/login", data={
        "username": "ghost",
        "password": "whatever1",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_protected_route_without_token(client):
    """A protected route returns 401 when no bearer token is supplied."""
    response = client.get("/users/me")
    assert response.status_code == 401


# ── UC-1: bcrypt password hashing ─────────────────────────────────────────────

def test_stored_hash_is_bcrypt(client, db):
    """The password stored on registration is a bcrypt hash ($2b$), not the
    plaintext (and not the old 32-char MD5 hex).

    The stored hash is read directly from the shared in-memory DB session rather
    than from ``/users/me``, so this end-to-end check does not depend on
    ``UserOut`` leaking ``password_hash`` over the API.
    """
    from app import models

    plaintext = "supersecret1"
    register = client.post("/auth/register", json={
        "username": "bcryptuser",
        "email": "bcrypt@example.com",
        "password": plaintext,
    })
    assert register.status_code == 200

    user = (
        db.query(models.User)
        .filter(models.User.username == "bcryptuser")
        .first()
    )
    stored = user.password_hash
    assert stored.startswith("$2b$")
    assert plaintext not in stored


def test_hash_password_starts_with_2b():
    """hash_password produces a bcrypt $2b$ hash that omits the plaintext."""
    from app.routers.auth import hash_password

    plaintext = "anothersecret1"
    hashed = hash_password(plaintext)
    assert hashed.startswith("$2b$")
    assert plaintext not in hashed


def test_hash_password_is_salted():
    """Hashing the same password twice yields different hashes (random salt)."""
    from app.routers.auth import hash_password

    assert hash_password("samepassword1") != hash_password("samepassword1")


def test_verify_password_roundtrip():
    """verify_password is True for the correct password and False otherwise."""
    from app.routers.auth import hash_password, verify_password

    hashed = hash_password("correcthorse1")
    assert verify_password("correcthorse1", hashed) is True
    assert verify_password("wrongpassword1", hashed) is False
