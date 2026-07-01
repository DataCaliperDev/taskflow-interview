# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.enums import UserRole
from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client(reset_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user_token(client):
    """Register and log in a test user, returning a bearer token."""
    client.post("/auth/register", json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpass",
    })
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    return response.json()["access_token"]


@pytest.fixture
def other_user_token(client):
    """Register and log in a second regular user, returning a bearer token."""
    client.post("/auth/register", json={
        "username": "otheruser",
        "email": "otheruser@example.com",
        "password": "otherpass",
    })
    response = client.post(
        "/auth/login",
        data={"username": "otheruser", "password": "otherpass"},
    )
    return response.json()["access_token"]


@pytest.fixture
def admin_user_token(client):
    """Register a user, elevate to admin via DB, and return a bearer token."""
    client.post("/auth/register", json={
        "username": "adminuser",
        "email": "adminuser@example.com",
        "password": "adminpass",
    })
    from app import models as m
    db = TestingSessionLocal()
    try:
        user = db.query(m.User).filter(m.User.username == "adminuser").first()
        user.role = UserRole.ADMIN
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/auth/login",
        data={"username": "adminuser", "password": "adminpass"},
    )
    return response.json()["access_token"]


@pytest.fixture
def created_task(client, test_user_token):
    """Create a task as testuser and return the response JSON."""
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    return response.json()
