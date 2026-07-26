# tests/conftest.py

import pytest

from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.routers.auth import hash_password

load_dotenv(".env.test", override=True)


from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.database import Base, get_db
from app.models import User, Task, Comment

# Issue: uses a separate in-memory DB, but does not reset between individual tests
# — tests that mutate data will bleed state into later tests
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def sample_data(session):
    # Create users
    alice = User(username="alice", email="alice@example.com",
                password_hash=hash_password("alice123"), role="admin")
    bob = User(username="bob", email="bob@example.com",
            password_hash=hash_password("bob123"), role="member")
    carol = User(username="carol", email="carol@example.com",
                password_hash=hash_password("carol123"), role="member")

    session.add_all([alice, bob, carol])
    session.commit()

    # Create tasks
    tasks_data = [
        Task(title="Set up CI/CD pipeline", description="Configure GitHub Actions for automated testing.",
            status="in_progress", priority=3, owner_id=alice.id,
            tags="devops,infra", due_date=datetime.utcnow() + timedelta(days=3)),
        Task(title="Write API documentation", description="Document all endpoints using OpenAPI.",
            status="todo", priority=2, owner_id=alice.id, tags="docs"),
        Task(title="Fix login page bug", description="Users are redirected to a blank page after login.",
            status="todo", priority=3, owner_id=bob.id,
            due_date=datetime.utcnow() - timedelta(days=1)),  # overdue
        Task(title="Add unit tests for helpers", description=None,
            status="todo", priority=1, owner_id=bob.id, tags="testing"),
        Task(title="Migrate database to Postgres", description="Move from SQLite to PostgreSQL for production.",
            status="done", priority=2, owner_id=carol.id, tags="db,infra"),
        Task(title="Code review for PR #42", description=None,
            status="done", priority=1, owner_id=carol.id),
    ]

    session.add_all(tasks_data)
    session.commit()

    # Add comments
    comments = [
        Comment(content="Started the pipeline setup — blocked on secrets config.",
                task_id=tasks_data[0].id, author_id=bob.id),
        Comment(content="Docs template is in Confluence, linking there.",
                task_id=tasks_data[1].id, author_id=carol.id),
    ]
    session.add_all(comments)
    session.commit()

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables once per test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_sample_data():
    session = Session(engine)
    sample_data(session)
    session.close()


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
