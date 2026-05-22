# tests/conftest.py

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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


# Reset the schema at the start of every test session so the suite is
# repeatable. Without this, `test.db` keeps state from the previous run —
# e.g. `test_update_user` renames `testuser`, which then breaks the
# `test_user_token` fixture on the very next invocation (causing every
# downstream test to error with `KeyError: 'access_token'`). UC-3's victim
# registrations have the same problem on re-runs.
@pytest.fixture(scope="session", autouse=True)
def _reset_db_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


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


# ── UC-5 helper ──────────────────────────────────────────────────────────────
# Generic SQL-query counter used to prove the absence of N+1 patterns.
# Hooks SQLAlchemy's `before_cursor_execute` event for the duration of the
# context block and returns a dict with the running count.


@pytest.fixture
def query_counter():
    @contextmanager
    def _counter():
        counter = {"n": 0}

        def _on_execute(conn, cursor, statement, params, context, executemany):
            counter["n"] += 1

        event.listen(engine, "before_cursor_execute", _on_execute)
        try:
            yield counter
        finally:
            event.remove(engine, "before_cursor_execute", _on_execute)

    return _counter


# Issue: no fixture for DB teardown — test.db file persists after the suite runs
