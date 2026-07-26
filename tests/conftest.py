# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers.auth import hash_password

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_user(username: str, email: str, password: str, role: str = "member"):
    db = TestingSessionLocal()
    try:
        user = (
            db.query(models.User)
            .filter((models.User.username == username) | (models.User.email == email))
            .first()
        )
        if user is None:
            user = models.User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=role,
            )
            db.add(user)
        else:
            user.username = username
            user.email = email
            user.password_hash = hash_password(password)
            user.role = role
            user.is_active = True
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def ensure_task(title: str, owner_id: int, status: str = "todo"):
    db = TestingSessionLocal()
    try:
        task = db.query(models.Task).filter(models.Task.title == title).first()
        if task is None:
            task = models.Task(title=title, owner_id=owner_id, status=status, priority=2)
            db.add(task)
        else:
            task.owner_id = owner_id
            task.status = status
            task.priority = 2
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def test_user():
    return ensure_user("testuser", "testuser@example.com", "testpass", role="member")


@pytest.fixture()
def admin_user():
    return ensure_user("adminuser", "adminuser@example.com", "adminpass", role="admin")


@pytest.fixture()
def member_target_user():
    return ensure_user("targetuser", "targetuser@example.com", "targetpass", role="member")


@pytest.fixture()
def delete_victim_user():
    return ensure_user("deletevictim", "deletevictim@example.com", "victimpass", role="member")


@pytest.fixture()
def test_user_token(client, test_user):
    response = client.post(
        "/auth/login",
        data={"username": test_user.username, "password": "testpass"},
    )
    return response.json()["access_token"]


@pytest.fixture()
def admin_user_token(client, admin_user):
    response = client.post(
        "/auth/login",
        data={"username": admin_user.username, "password": "adminpass"},
    )
    return response.json()["access_token"]


@pytest.fixture()
def member_target_token(client, member_target_user):
    response = client.post(
        "/auth/login",
        data={"username": member_target_user.username, "password": "targetpass"},
    )
    return response.json()["access_token"]


@pytest.fixture()
def test_user_task(client, test_user_token):
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    return response.json()


@pytest.fixture()
def admin_owned_task(admin_user):
    return ensure_task("Admin-owned authorization task", admin_user.id)


@pytest.fixture()
def member_owned_task(test_user):
    return ensure_task("Member-owned authorization task", test_user.id)


@pytest.fixture()
def member_delete_task(test_user):
    return ensure_task("Member-owned delete authorization task", test_user.id)


@pytest.fixture()
def delete_victim_task(delete_victim_user):
    return ensure_task("Delete-victim task", delete_victim_user.id)
