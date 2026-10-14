# tests/conftest.py

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./taskflow.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import User
from app.routers.auth import hash_password

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_user_token(client):
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


@pytest.fixture(scope="function")
def auth_headers(test_user_token):
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture(scope="function")
def created_task(client, auth_headers):
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="function")
def other_auth_headers(client):
    client.post("/auth/register", json={
        "username": "otheruser",
        "email": "other@example.com",
        "password": "otherpass",
    })
    response = client.post(
        "/auth/login",
        data={"username": "otheruser", "password": "otherpass"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="function")
def db(client):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def admin_headers(client):
    db = TestingSessionLocal()
    admin = User(
        username="adminuser",
        email="admin@example.com",
        password_hash=hash_password("adminpass"),
        role="admin",
    )
    db.add(admin)
    db.commit()
    db.close()

    response = client.post(
        "/auth/login",
        data={"username": "adminuser", "password": "adminpass"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
