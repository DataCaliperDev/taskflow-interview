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
