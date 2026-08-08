# tests/conftest.py

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.main import app
from app.database import Base, get_db

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


@pytest.fixture()
def db_session():
    """Direct DB access for assertions about stored rows.

    Added for UC-1: proving a hash is safe means checking what was written to
    the users table, not what the API echoed back. Shares the test database with
    `client`, so each sees the other's commits.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def make_user(client, db_session):
    """Factory: create a user with a given role, return (user_body, auth_header).

    Added for UC-3, which needs three distinct actors (owner, someone else, an
    admin) per test. Names are generated per call so tests stay independent of
    each other and of previous runs.

    The role is set on the row directly because there is no endpoint that grants
    one — and deliberately so, since a self-service role change would be the
    privilege escalation this use case exists to prevent.
    """
    def _make(prefix="user", role="member"):
        username = f"{prefix}-{uuid.uuid4().hex[:8]}"
        password = "authz-test-password"

        user = client.post("/auth/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        }).json()

        if role != "member":
            row = db_session.query(models.User).filter(
                models.User.id == user["id"]
            ).first()
            row.role = role
            db_session.commit()

        token = client.post("/auth/login", data={
            "username": username,
            "password": password,
        }).json()["access_token"]

        return user, {"Authorization": f"Bearer {token}"}

    return _make


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


# Issue: no fixture for DB teardown — test.db file persists after the suite runs
