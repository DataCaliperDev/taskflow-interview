# tests/conftest.py

import os

# Settings is loaded at import time and requires SECRET_KEY.
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def client(db_session):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def test_user_token(client):
    """Register and log in a default test user, returning a bearer token."""
    client.post("/auth/register", json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpass1",
    })
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass1"},
    )
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def authed_client(client, test_user_token):
    """TestClient that automatically sends the bearer token."""
    client.headers.update({"Authorization": f"Bearer {test_user_token}"})
    return client
