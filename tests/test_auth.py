# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""


def test_register(client):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "newuserpw",  # UC-9: passwords must be ≥ 8 chars
    })
    assert response.status_code == 200
    # UC-2: registration response must not leak the password hash.
    assert "password_hash" not in response.json()


def test_register_duplicate_email(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "duppass123",
    })
    response = client.post("/auth/register", json={
        "username": "dupuser2",
        "email": "dup@example.com",
        "password": "duppass456",
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


# ── UC-9: input validation on UserCreate ─────────────────────────────────────
# Each rule is exercised with both a valid input (so we know the constraint
# isn't accidentally rejecting good payloads) and at least one invalid input
# (so we know the constraint actually fires). A 422 response from FastAPI
# means a Pydantic ValidationError reached the boundary.


def test_register_rejects_short_username(client):
    response = client.post("/auth/register", json={
        "username": "ab",  # 2 chars, below the 3-char minimum
        "email": "shortname@example.com",
        "password": "longenough",
    })
    assert response.status_code == 422
    body = response.json()
    # Pydantic returns structured per-field errors; one of them must be on `username`.
    assert any("username" in err["loc"] for err in body["detail"])


def test_register_accepts_minimum_length_username(client):
    response = client.post("/auth/register", json={
        "username": "abc",  # exactly 3 chars — boundary value
        "email": "abc@example.com",
        "password": "longenough",
    })
    assert response.status_code == 200


def test_register_rejects_short_password(client):
    response = client.post("/auth/register", json={
        "username": "shortpw_user",
        "email": "shortpw@example.com",
        "password": "abc1234",  # 7 chars, below the 8-char minimum
    })
    assert response.status_code == 422
    assert any("password" in err["loc"] for err in response.json()["detail"])


def test_register_accepts_minimum_length_password(client):
    response = client.post("/auth/register", json={
        "username": "minpw_user",
        "email": "minpw@example.com",
        "password": "abcd1234",  # exactly 8 chars — boundary value
    })
    assert response.status_code == 200


def test_register_rejects_malformed_email(client):
    response = client.post("/auth/register", json={
        "username": "bademail_user",
        "email": "not-an-email",
        "password": "longenough",
    })
    assert response.status_code == 422
    assert any("email" in err["loc"] for err in response.json()["detail"])


def test_register_accepts_well_formed_email(client):
    response = client.post("/auth/register", json={
        "username": "goodemail_user",
        "email": "goodemail+tag@example.co.uk",
        "password": "longenough",
    })
    assert response.status_code == 200
