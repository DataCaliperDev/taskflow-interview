# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app import models

# Issue: uses a separate in-memory DB, but does not reset between individual tests
# — tests that mutate data will bleed state into later tests
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")  # Issue: module scope means DB state leaks between tests
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
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


# ── UC-3 fixtures ────────────────────────────────────────────────────────────
# Authorisation tests need three distinct identities: an owner (test_user_token
# above), a different non-owner member, and an admin. The /auth/register
# endpoint doesn't accept a `role` parameter (and shouldn't — that would be a
# privilege-escalation hole on its own), so the admin's role is promoted
# directly via the test DB session after registration.


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def other_user_token(client):
    """A second normal member, used to assert non-owners are blocked."""
    client.post("/auth/register", json={
        "username": "other_user",
        "email": "other@example.com",
        "password": "otherpass",
    })
    return _login(client, "other_user", "otherpass")


@pytest.fixture(scope="module")
def admin_token(client):
    """An admin user. Role is promoted via the DB because /auth/register
    intentionally does not expose role assignment."""
    client.post("/auth/register", json={
        "username": "admin_user",
        "email": "admin@example.com",
        "password": "adminpass",
    })
    db = TestingSessionLocal()
    try:
        user = (
            db.query(models.User)
            .filter(models.User.username == "admin_user")
            .first()
        )
        user.role = "admin"
        db.commit()
    finally:
        db.close()
    return _login(client, "admin_user", "adminpass")


# Issue: no fixture for DB teardown — test.db file persists after the suite runs
