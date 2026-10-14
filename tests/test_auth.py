# tests/test_auth.py

"""
Tests for the /auth endpoints.
"""

from datetime import timedelta

from jose import jwt

from app.config import settings
from app.routers.auth import create_access_token
from tests.conftest import auth_headers_for


def _register(client, username="newuser", email="new@example.com", password="newpass123"):
    return client.post("/auth/register", json={
        "username": username, "email": email, "password": password,
    })


def test_register(client):
    response = _register(client)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["id"], int)
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["role"] == "member"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "password_hash" not in data


def test_register_duplicate_email(client):
    _register(client, username="dupuser", email="dup@example.com")

    response = _register(client, username="dupuser2", email="dup@example.com")

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_missing_field(client):
    response = client.post("/auth/register", json={
        "username": "noemail", "password": "password123",
    })

    assert response.status_code == 422
    assert any(err["loc"] == ["body", "email"] for err in response.json()["detail"])


def test_login_success(client):
    _register(client, username="loginuser", email="login@example.com", password="mypassword")

    response = client.post("/auth/login", data={
        "username": "loginuser", "password": "mypassword",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    claims = jwt.decode(body["access_token"], settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM])
    assert claims["sub"] == "loginuser"
    assert "exp" in claims


def test_login_wrong_password(client, user):
    response = client.post("/auth/login", data={
        "username": user.username, "password": "wrongpassword",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_unknown_user(client):
    response = client.post("/auth/login", data={
        "username": "ghost", "password": "whatever123",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_protected_route_without_token(client):
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_protected_route_with_invalid_token(client):
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_protected_route_with_expired_token(client, user):
    token = create_access_token({"sub": user.username}, expires_delta=timedelta(seconds=-1))

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_inactive_user_is_rejected(client, make_user):
    inactive = make_user("sleepy", is_active=False)

    response = client.get("/users/me", headers=auth_headers_for(inactive))

    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"
