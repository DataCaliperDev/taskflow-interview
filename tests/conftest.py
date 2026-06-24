import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.routers.auth import hash_password


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def make_user(db_session):
    counter = itertools.count(1)

    def _make_user(username=None, email=None, password="password123", role="member"):
        suffix = next(counter)
        username = username or f"user{suffix}"
        email = email or f"{username}@example.com"
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture
def auth_headers(client, make_user):
    def _auth_headers(username="testuser", password="password123", role="member"):
        user = make_user(username=username, password=password, role=role)
        response = client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}, user

    return _auth_headers
