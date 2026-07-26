"""
Tests for TaskCreate, TaskUpdate, and UserCreate Pydantic validators.

Adjust the import below to match where your schemas actually live,
e.g. `from app.schemas import TaskCreate, TaskUpdate, UserCreate`.
"""

import pytest
from pydantic import ValidationError

from app.schemas import TaskCreate, TaskUpdate, UserCreate


# ---------------------------------------------------------------------------
# TaskCreate: status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
def test_task_create_valid_status(status):
    task = TaskCreate(title="Write report", status=status)
    assert task.status == status


@pytest.mark.parametrize("status", ["not_a_status", "TODO", "completed", ""])
def test_task_create_invalid_status(status):
    with pytest.raises(ValidationError):
        TaskCreate(title="Write report", status=status)


# ---------------------------------------------------------------------------
# TaskCreate: priority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("priority", [1, 2, 3])
def test_task_create_valid_priority(priority):
    task = TaskCreate(title="Write report", priority=priority)
    assert task.priority == priority


@pytest.mark.parametrize("priority", [0, 4, -1, 100])
def test_task_create_invalid_priority(priority):
    with pytest.raises(ValidationError):
        TaskCreate(title="Write report", priority=priority)


# ---------------------------------------------------------------------------
# TaskCreate: title minimum length
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", ["A", "Write report", "x" * 200])
def test_task_create_valid_title(title):
    task = TaskCreate(title=title)
    assert task.title == title


def test_task_create_invalid_title_empty():
    with pytest.raises(ValidationError):
        TaskCreate(title="")


def test_task_create_invalid_title_whitespace_only():
    with pytest.raises(ValidationError):
        TaskCreate(title="   ")


# ---------------------------------------------------------------------------
# TaskUpdate: status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
def test_task_update_valid_status(status):
    task = TaskUpdate(status=status)
    assert task.status == status


@pytest.mark.parametrize("status", ["archived", "DONE", "pending"])
def test_task_update_invalid_status(status):
    with pytest.raises(ValidationError):
        TaskUpdate(status=status)


def test_task_update_status_none_is_allowed():
    """status is optional on updates, so None should pass through untouched."""
    task = TaskUpdate(status=None)
    assert task.status is None


# ---------------------------------------------------------------------------
# TaskUpdate: priority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("priority", [1, 2, 3])
def test_task_update_valid_priority(priority):
    task = TaskUpdate(priority=priority)
    assert task.priority == priority


@pytest.mark.parametrize("priority", [0, 4, -5, 10])
def test_task_update_invalid_priority(priority):
    with pytest.raises(ValidationError):
        TaskUpdate(priority=priority)


def test_task_update_priority_none_is_allowed():
    task = TaskUpdate(priority=None)
    assert task.priority is None


# ---------------------------------------------------------------------------
# TaskUpdate: title minimum length (when provided)
# ---------------------------------------------------------------------------

def test_task_update_valid_title():
    task = TaskUpdate(title="Updated title")
    assert task.title == "Updated title"


def test_task_update_title_none_is_allowed():
    task = TaskUpdate(title=None)
    assert task.title is None


def test_task_update_invalid_title_empty():
    with pytest.raises(ValidationError):
        TaskUpdate(title="")


def test_task_update_invalid_title_whitespace_only():
    with pytest.raises(ValidationError):
        TaskUpdate(title="   ")


# ---------------------------------------------------------------------------
# UserCreate: email format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "email",
    ["alice@example.com", "bob.smith@sub.example.co.uk", "user+tag@example.com"],
)
def test_user_create_valid_email(email):
    user = UserCreate(username="alice", email=email, password="secret123")
    assert user.email == email


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "alice@", "@example.com", "alice.com", "alice@@example.com", ""],
)
def test_user_create_invalid_email(email):
    with pytest.raises(ValidationError):
        UserCreate(username="alice", email=email, password="secret123")


# ---------------------------------------------------------------------------
# UserCreate: username minimum length (>= 3 chars)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("username", ["bob", "alice", "a" * 50])
def test_user_create_valid_username(username):
    user = UserCreate(username=username, email="bob@example.com", password="secret123")
    assert user.username == username


@pytest.mark.parametrize("username", ["", "a", "ab"])
def test_user_create_invalid_username(username):
    with pytest.raises(ValidationError):
        UserCreate(username=username, email="bob@example.com", password="secret123")


# ---------------------------------------------------------------------------
# UserCreate: password minimum length (>= 8 chars)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("password", ["12345678", "supersecretpassword", "a" * 8])
def test_user_create_valid_password(password):
    user = UserCreate(username="carol", email="carol@example.com", password=password)
    assert user.password == password


@pytest.mark.parametrize("password", ["", "short", "1234567"])
def test_user_create_invalid_password(password):
    with pytest.raises(ValidationError):
        UserCreate(username="carol", email="carol@example.com", password=password)


# ---------------------------------------------------------------------------
# Combined / sanity checks
# ---------------------------------------------------------------------------

def test_task_create_defaults_are_valid():
    """Defaults (status='todo', priority=2) must themselves pass validation."""
    task = TaskCreate(title="Default task")
    assert task.status == "todo"
    assert task.priority == 2


def test_user_create_all_fields_valid_together():
    user = UserCreate(username="dave", email="dave@example.com", password="mypassword1")
    assert user.username == "dave"
    assert user.email == "dave@example.com"
    assert user.password == "mypassword1"
