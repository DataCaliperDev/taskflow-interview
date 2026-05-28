"""Test fixtures -- UC-12.

Three problems the original suite had:

    1. Tests shared state. A module-scoped client and an on-disk
       database meant earlier tests left rows behind that later
       tests accidentally relied on.
    2. Test order mattered. ``test_tasks.py`` carried a global
       ``created_task_id`` -- delete the create test and the rest
       broke.
    3. Assertions only checked status codes, not response bodies.

This conftest replaces all three:

    - The database lives only in memory and is wiped between every
      test, so tests cannot leak into each other.
    - Each test logs in fresh: ``alice`` (admin), ``bob`` and
      ``carol`` (members) are seeded by a fixture, and there is a
      bearer-token fixture for each.
    - A ``make_task`` factory creates a task on demand and returns
      its full response body, so a test that needs an existing task
      no longer reaches for a global.

Tests that need to assert on response shape do so against the body
the fixtures hand back.
"""

import os

# UC-4: the application refuses to import without a signing secret.
# Inject one before any application module loads so the test runner
# does not need a populated ``.env``.
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-long-enough-1234")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.routers.auth import hash_password


@pytest.fixture()
def db_engine():
    """A fresh database for one test, gone afterwards."""
    engine = create_engine(
        # In-memory; the StaticPool below makes the test client and
        # any direct session see the same connection (otherwise
        # in-memory SQLite gives each connection its own empty store).
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Direct session for fixtures that seed rows without going
    through the HTTP layer."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    """A test client wired to this test\'s database. The override is
    removed afterwards so it cannot leak into another test."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def seeded_users(db_session):
    """The standing cast: alice (admin), bob and carol (members).
    Mirrors the credentials documented in TASKS.md so authorization
    tests can refer to roles by name."""
    alice = User(username="alice", email="alice@example.com",
                 password_hash=hash_password("alice123"), role="admin")
    bob = User(username="bob", email="bob@example.com",
               password_hash=hash_password("bob123"), role="member")
    carol = User(username="carol", email="carol@example.com",
                 password_hash=hash_password("carol123"), role="member")
    db_session.add_all([alice, bob, carol])
    db_session.commit()
    db_session.refresh(alice)
    db_session.refresh(bob)
    db_session.refresh(carol)
    return {"alice": alice, "bob": bob, "carol": carol}


def _login(client, username: str, password: str) -> str:
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_token(client, seeded_users):
    return _login(client, "alice", "alice123")


@pytest.fixture()
def bob_token(client, seeded_users):
    return _login(client, "bob", "bob123")


@pytest.fixture()
def carol_token(client, seeded_users):
    return _login(client, "carol", "carol123")


@pytest.fixture()
def auth_header():
    """Build the bearer-token header for a given access token."""
    def _factory(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}
    return _factory


@pytest.fixture()
def make_task(client, auth_header):
    """Create a task on demand and return its body. Replaces the
    global ``created_task_id`` -- every test owns the tasks it needs."""
    def _factory(token: str, **overrides) -> dict:
        payload = {"title": "Sample", "priority": 2, "status": "todo"}
        payload.update(overrides)
        resp = client.post("/tasks/", json=payload, headers=auth_header(token))
        assert resp.status_code == 201, resp.text
        return resp.json()
    return _factory
