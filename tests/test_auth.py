# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""


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


def test_password_is_irreversible(client):
    """Verify that a plaintext password cannot be retrieved from the stored hash."""
    plaintext = "irreversible_secret"

    # Register a user and get back the stored hash from the response
    response = client.post("/auth/register", json={
        "username": "hashcheckuser",
        "email": "hashcheck@example.com",
        "password": plaintext,
    })
    assert response.status_code == 200
    stored_hash = response.json()["password_hash"]

    # 1. Hash is not the plaintext itself
    assert stored_hash != plaintext

    # 2. Hash does not contain the plaintext as a substring
    assert plaintext not in stored_hash

    # 3. Hash is not a hex string of the plaintext (rules out MD5/SHA family)
    import hashlib
    assert stored_hash != hashlib.md5(plaintext.encode()).hexdigest()
    assert stored_hash != hashlib.sha1(plaintext.encode()).hexdigest()
    assert stored_hash != hashlib.sha256(plaintext.encode()).hexdigest()

    # 4. Stored hash is a valid bcrypt hash (starts with bcrypt identifier)
    assert stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")

    # 5. Two hashes of the same password are different (salt is unique per call)
    from app.routers.auth import hash_password
    hash_a = hash_password(plaintext)
    hash_b = hash_password(plaintext)
    assert hash_a != hash_b

    # 6. Correct password verifies successfully against the stored hash
    from app.routers.auth import verify_password
    assert verify_password(plaintext, stored_hash) is True

    # 7. Wrong password does not verify
    assert verify_password("wrong_password", stored_hash) is False
