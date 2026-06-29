import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

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
def reset_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_and_login(client, username="testuser", password="testpass123",
                       email=None, role="member"):
    email = email or f"{username}@example.com"
    client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
    })
    if role != "member":
        from app.models import User
        session = TestingSessionLocal()
        user = session.query(User).filter(User.username == username).first()
        user.role = role
        session.commit()
        session.close()
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    return response.json()["access_token"]


@pytest.fixture
def test_user_token(client):
    return register_and_login(client)


@pytest.fixture
def admin_token(client):
    return register_and_login(client, username="adminuser", role="admin")


@pytest.fixture
def auth_headers(test_user_token):
    return {"Authorization": f"Bearer {test_user_token}"}
