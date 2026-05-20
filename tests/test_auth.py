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


def test_password_hash_not_in_response(client):
    """Verify that password_hash is never returned in any user-facing response."""
    plaintext = "irreversible_secret"

    # POST /auth/register
    register_response = client.post("/auth/register", json={
        "username": "hashcheckuser",
        "email": "hashcheck@example.com",
        "password": plaintext,
    })
    assert register_response.status_code == 200
    assert "password_hash" not in register_response.json()

    # Obtain a token for authenticated endpoints
    login_response = client.post("/auth/login", data={
        "username": "hashcheckuser",
        "password": plaintext,
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /users/me
    me_response = client.get("/users/me", headers=headers)
    assert me_response.status_code == 200
    assert "password_hash" not in me_response.json()

    # GET /users/
    list_response = client.get("/users/", headers=headers)
    assert list_response.status_code == 200
    for user in list_response.json():
        assert "password_hash" not in user

    # GET /users/{id}
    user_id = register_response.json()["id"]
    get_response = client.get(f"/users/{user_id}", headers=headers)
    assert get_response.status_code == 200
    assert "password_hash" not in get_response.json()


def test_password_is_irreversible(client):
    """Verify that a plaintext password cannot be retrieved from the stored hash."""
    import hashlib
    from app.routers.auth import hash_password, verify_password

    plaintext = "irreversible_secret"
    stored_hash = hash_password(plaintext)

    # 1. Hash is not the plaintext itself
    assert stored_hash != plaintext

    # 2. Hash does not contain the plaintext as a substring
    assert plaintext not in stored_hash

    # 3. Hash is not a hex string of the plaintext (rules out MD5/SHA family)
    assert stored_hash != hashlib.md5(plaintext.encode()).hexdigest()
    assert stored_hash != hashlib.sha1(plaintext.encode()).hexdigest()
    assert stored_hash != hashlib.sha256(plaintext.encode()).hexdigest()

    # 4. Stored hash is a valid bcrypt hash (starts with bcrypt identifier)
    assert stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")

    # 5. Two hashes of the same password are different (salt is unique per call)
    hash_a = hash_password(plaintext)
    hash_b = hash_password(plaintext)
    assert hash_a != hash_b

    # 6. Correct password verifies successfully against the stored hash
    assert verify_password(plaintext, stored_hash) is True

    # 7. Wrong password does not verify
    assert verify_password("wrong_password", stored_hash) is False
