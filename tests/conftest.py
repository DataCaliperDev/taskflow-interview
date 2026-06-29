# tests/conftest.py

"""
Test fixtures for the TaskFlow suite.

Isolation strategy (UC-12):
- A single in-memory SQLite database shared across connections via ``StaticPool``
  (a brand-new on-disk ``test.db`` is never touched).
- The schema is dropped and recreated for **every** test via a function-scoped
  ``db`` fixture, so no state bleeds between tests.
- ``get_db`` is overridden to yield the per-test session; tests and the app share
  the same session, which lets later UCs seed rows directly through the fixture.
- ``TestClient(app)`` is created **without** the ``with`` context manager on
  purpose: entering the context would fire the app's ``startup`` hook
  (``init_db()``), which creates tables on the real on-disk file engine. The test
  engine's tables are created by the fixture instead.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

# In-memory DB shared across connections (StaticPool keeps a single connection).
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _register_and_login(client, username, email, password):
    """Register a user then log it in; return the access token.

    Collapses the register+login boilerplate shared by the token fixtures.
    """
    client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def db():
    """Fresh schema + session per test — guarantees no cross-test state."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """TestClient wired to the per-test session via a dependency override."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # NOTE: no `with TestClient(app)` — avoids triggering the startup hook that
    # would init the real file-backed DB.
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user_token(client):
    """Register + log in a fresh user each test; return its bearer token.

    Password is >= 8 chars so the fixture survives UC-9's length validation.
    """
    return _register_and_login(
        client, "testuser", "testuser@example.com", "testpass1"
    )


@pytest.fixture(scope="function")
def auth_headers(test_user_token):
    """Authorization header for the fixture user."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture(scope="function")
def second_user_token(client):
    """Register + log in a SECOND, non-owner member; return its bearer token.

    Used by UC-3 tests to assert a different non-admin user is forbidden from
    modifying another user's tasks/profile.
    """
    return _register_and_login(
        client, "otheruser", "otheruser@example.com", "otherpass1"
    )


@pytest.fixture(scope="function")
def second_auth_headers(second_user_token):
    """Authorization header for the second (non-owner) member."""
    return {"Authorization": f"Bearer {second_user_token}"}


@pytest.fixture(scope="function")
def admin_token(client, db):
    """Register a user, promote it to ``role='admin'`` directly via the db
    session (there is no API to set the role), then log in and return its token.
    """
    from app import models

    token = _register_and_login(
        client, "adminuser", "adminuser@example.com", "adminpass1"
    )
    admin = (
        db.query(models.User)
        .filter(models.User.username == "adminuser")
        .first()
    )
    admin.role = "admin"
    db.commit()
    return token


@pytest.fixture(scope="function")
def admin_auth_headers(admin_token):
    """Authorization header for the admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="function")
def created_task(client, auth_headers):
    """Create a task and RETURN it (replaces the old module-global task id)."""
    response = client.post(
        "/tasks/",
        json={
            "title": "Fixture Task",
            "description": "created by fixture",
            "priority": 2,
            "status": "todo",
        },
        headers=auth_headers,
    )
    return response.json()
