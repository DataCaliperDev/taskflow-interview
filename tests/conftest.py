# tests/conftest.py

import pytest

from dotenv import load_dotenv

load_dotenv(".env.test", override=True)


from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Issue: uses a separate in-memory DB, but does not reset between individual tests
# — tests that mutate data will bleed state into later tests
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables once per test session."""
    Base.metadata.create_all(bind=engine)
    import scripts.seed_data
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Wraps each individual test in an isolated transaction block."""
    connection = engine.connect()
    transaction = connection.begin()
    # Bind a session to the active connection
    session = TestingSessionLocal(bind=connection)

    yield session

    # Roll back everything done during the test execution
    session.close()
    transaction.rollback()
    connection.close()


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


@pytest.fixture(scope="module")
def test_admin_token(client):
    # Authenticate as admin (alice)
    response = client.post("/auth/login", data={
        "username": "alice",
        "password": "alice123"
    })
    response_content = response.json()
    token = response_content.get("access_token")
    return token


@pytest.fixture(scope="module")
def test_bob_token(client):
    # Authenticate  a member (bob)
    response = client.post("/auth/login", data={
        "username": "bob",
        "password": "bob123"
    })
    response_content = response.json()
    token = response_content.get("access_token")
    return token


@pytest.fixture(scope="module")
def test_carol_token(client):
    # Authenticate  a member (bob)
    response = client.post("/auth/login", data={
        "username": "carol",
        "password": "carol123"
    })
    response_content = response.json()
    token = response_content.get("access_token")
    return token


# Issue: no fixture for DB teardown — test.db file persists after the suite runs
