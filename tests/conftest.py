# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.main import app
from app.database import Base, get_db

DEFAULT_PASSWORD = "test-password"


@pytest.fixture()
def db_engine():
    """A fresh database per test, dropped afterwards.

    In memory rather than a file on disk, so nothing outlives the test that
    created it — the previous test.db kept rows between runs, which is why the
    suite passed once and then failed on the second run.

    StaticPool is what makes in-memory usable here: an in-memory SQLite
    database belongs to the connection that opened it, so without a single
    reused connection the application and the test would each get their own
    empty one.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Direct database access, for assertions about what was actually stored."""
    session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine):
    """A TestClient talking to this test's database.

    Built without the context manager deliberately: entering it fires the app's
    startup event, which calls init_db() against the real engine and would
    create tables in taskflow.db on every single test.

    The dependency override is removed afterwards so it cannot leak into a test
    that did not ask for a client.
    """
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def _get_test_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def make_user(client, db_session):
    """Factory: create a user with a given role, return (user_body, auth_header).

    Names are numbered per test rather than randomised — the database is empty
    at the start of every test, so uniqueness only has to hold within one, and
    "owner1" reads better than a uuid fragment in a failure message.

    The role is set on the row directly because no endpoint grants one, and
    deliberately so: a self-service role change would be the privilege
    escalation the authorization rules exist to prevent.
    """
    created = 0

    def _make(prefix="user", role="member", password=DEFAULT_PASSWORD):
        nonlocal created
        created += 1
        username = f"{prefix}{created}"

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


@pytest.fixture()
def make_task(client):
    """Factory: create a task owned by the holder of `auth`, return its body.

    Replaces the module-level created_task_id that used to chain the task tests
    together — each test now creates what it needs and is handed the result.
    """
    def _make(auth, **overrides):
        payload = {"title": "Test task", "priority": 2, "status": "todo"}
        payload.update(overrides)

        response = client.post("/tasks/", json=payload, headers=auth)
        assert response.status_code == 200, response.text
        return response.json()

    return _make
