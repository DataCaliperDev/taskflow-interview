from app.models import User
from app.routers.auth import verify_password


def test_register_hashes_password_and_hides_hash(client, db_session):
    response = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123",
    })

    assert response.status_code == 200
    assert "password_hash" not in response.json()

    user = db_session.query(User).filter(User.username == "newuser").one()
    assert user.password_hash != "password123"
    assert "password123" not in user.password_hash
    assert verify_password("password123", user.password_hash)


def test_register_duplicate_email(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "password123",
    })

    response = client.post("/auth/register", json={
        "username": "dupuser2",
        "email": "dup@example.com",
        "password": "password456",
    })

    assert response.status_code == 400


def test_register_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup1@example.com",
        "password": "password123",
    })

    response = client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup2@example.com",
        "password": "password456",
    })

    assert response.status_code == 400


def test_login_success(client, make_user):
    make_user(username="loginuser", password="mypassword")

    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "mypassword",
    })

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_wrong_password(client, make_user):
    make_user(username="loginuser", password="mypassword")

    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "wrongpassword",
    })

    assert response.status_code == 401


def test_register_validates_email_username_and_password(client):
    invalid_payloads = [
        {"username": "ab", "email": "valid@example.com", "password": "password123"},
        {"username": "validuser", "email": "not-an-email", "password": "password123"},
        {"username": "validuser", "email": "valid@example.com", "password": "short"},
    ]

    for payload in invalid_payloads:
        response = client.post("/auth/register", json=payload)
        assert response.status_code == 422
