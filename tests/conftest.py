# tests/conftest.py

"""
Pytest configuration and fixtures.

UC-12 — Test isolation
======================
Every test runs against a clean database. The autouse `_reset_db` fixture
drops and recreates all tables before each test, so no test depends on
state left behind by another test (no ordering dependencies, no shared
"created_task_id" globals, no need to register users at module level).

All public fixtures (`client`, `test_user_token`, `other_user_token`,
`admin_token`, `created_task`) are function-scoped. The cost is a per-test
schema reset that is well under 50 ms on SQLite — worth it for the
guarantee that any test can be run in any order.
"""

from contextlib import contextmanager
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app import models

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


# ── DB isolation (UC-12) ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_db():
    """Drop and recreate all tables before every test.

    Function-scoped + autouse, so no test needs to opt in. This is the
    teardown mechanism the previous module-scoped design was missing —
    tests can now mutate any row freely without affecting siblings.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


# ── Core fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    # Intentionally NOT used as a context manager: doing so triggers the
    # FastAPI lifespan startup/shutdown on every single test (~2.8 s each on
    # this codebase), which destroys the runtime budget under function-scoped
    # fixtures. The lifespan's only job is to call init_db(), and the
    # autouse `_reset_db` fixture already creates the schema ahead of every
    # test — so the lifespan is redundant for the test harness.
    return TestClient(app)


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    return response.json()["access_token"]


@pytest.fixture
def test_user_token(client):
    """Register and log in the default member user, return a bearer token."""
    client.post("/auth/register", json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpass",  # UC-9: must be ≥ 8 chars
    })
    return _login(client, "testuser", "testpass")


@pytest.fixture
def other_user_token(client):
    """A second normal member, used to assert non-owners are blocked."""
    client.post("/auth/register", json={
        "username": "other_user",
        "email": "other@example.com",
        "password": "otherpass",
    })
    return _login(client, "other_user", "otherpass")


@pytest.fixture
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


@dataclass
class CreatedTask:
    """Bundle returned by the `created_task` fixture so a test can grab
    everything it needs (task id + owning user's token) in one line."""
    id: int
    owner_token: str
    title: str
    status: str
    priority: int


@pytest.fixture
def created_task(client, test_user_token):
    """Create a task owned by `testuser`. Replaces the previous module-level
    `created_task_id` global that forced tests to run in a specific order."""
    payload = {"title": "fixture task", "priority": 2, "status": "todo"}
    response = client.post(
        "/tasks/",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return CreatedTask(
        id=body["id"],
        owner_token=test_user_token,
        title=body["title"],
        status=body["status"],
        priority=body["priority"],
    )


# ── UC-5 helper (kept) ───────────────────────────────────────────────────────
# Generic SQL-query counter used to prove the absence of N+1 patterns.


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
