# tests/conftest.py

import os

# Must be set before `app` is imported: settings are loaded at import time.
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-chars"
os.environ["DATABASE_URL"] = "sqlite://"  # keep the app engine off the real DB file

from functools import lru_cache  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.auth import create_access_token, hash_password  # noqa: E402

# In-memory SQLite shared across connections (StaticPool), so the app and
# the test code see the same data and nothing is written to disk.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _fresh_database():
    """Give every test an empty schema; drop it afterwards."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Users & auth ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _cached_hash(password: str) -> str:
    # bcrypt is intentionally slow; hash each fixture password only once
    return hash_password(password)


@pytest.fixture
def make_user(db_session):
    """Factory: insert a user directly and return the ORM object."""
    def _make_user(username, password="password123", role="member", is_active=True):
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            password_hash=_cached_hash(password),
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    return _make_user


def auth_headers_for(user) -> dict:
    token = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(make_user):
    return make_user("alice_member")


@pytest.fixture
def other_user(make_user):
    return make_user("bob_member")


@pytest.fixture
def admin(make_user):
    return make_user("carol_admin", role="admin")


@pytest.fixture
def user_headers(user):
    return auth_headers_for(user)


@pytest.fixture
def other_headers(other_user):
    return auth_headers_for(other_user)


@pytest.fixture
def admin_headers(admin):
    return auth_headers_for(admin)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_task(client):
    """Factory: create a task through the API and return the response JSON."""
    def _make_task(headers, **overrides):
        payload = {"title": "Test Task", "priority": 2, "status": "todo", **overrides}
        response = client.post("/tasks/", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()
    return _make_task


@pytest.fixture
def task(make_task, user_headers):
    """A task owned by `user`."""
    return make_task(user_headers, title="Write report", description="Q3 numbers")
