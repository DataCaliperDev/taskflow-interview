# tests/test_validation.py

"""
UC-9: input validation on user and task payloads.

Each rule is checked with valid and invalid inputs through the API, and the
error message is checked to point at the offending field.
"""

import pytest


def _errors_for(response, field):
    assert response.status_code == 422, response.text
    return [e["msg"] for e in response.json()["detail"] if e["loc"][-1] == field]


# ── UserCreate ────────────────────────────────────────────────────────────────

def _register(client, **overrides):
    payload = {"username": "validuser", "email": "valid@example.com",
               "password": "password123", **overrides}
    return client.post("/auth/register", json=payload)


@pytest.mark.parametrize("email", ["valid@example.com", "first.last+tag@sub.example.org"])
def test_register_accepts_valid_email(client, email):
    response = _register(client, email=email)

    assert response.status_code == 200
    assert response.json()["email"] == email


@pytest.mark.parametrize("email", ["not-an-email", "missing@", "@example.com", "a b@example.com", ""])
def test_register_rejects_invalid_email(client, email):
    msgs = _errors_for(_register(client, email=email), "email")

    assert msgs and "valid email address" in msgs[0]


@pytest.mark.parametrize("username", ["abc", "a" * 50])
def test_register_accepts_username_length_bounds(client, username):
    assert _register(client, username=username).status_code == 200


@pytest.mark.parametrize("username", ["", "ab", "  ab  ", "a" * 51])
def test_register_rejects_bad_username_length(client, username):
    msgs = _errors_for(_register(client, username=username), "username")

    assert msgs and ("at least 3 characters" in msgs[0] or "at most 50 characters" in msgs[0])


def test_register_accepts_8_char_password(client):
    assert _register(client, password="12345678").status_code == 200


@pytest.mark.parametrize("password", ["", "short", "1234567"])
def test_register_rejects_short_password(client, password):
    msgs = _errors_for(_register(client, password=password), "password")

    assert msgs == ["String should have at least 8 characters"]


# ── UserUpdate (same rules, optional fields) ─────────────────────────────────

@pytest.mark.parametrize("payload, field", [
    ({"username": "ab"}, "username"),
    ({"email": "nope"}, "email"),
    ({"password": "short"}, "password"),
])
def test_update_user_applies_same_rules(client, user, user_headers, payload, field):
    response = client.put(f"/users/{user.id}", json=payload, headers=user_headers)

    assert _errors_for(response, field)


def test_update_user_accepts_valid_values(client, user, user_headers):
    response = client.put(
        f"/users/{user.id}",
        json={"username": "newname", "email": "new@example.com", "password": "longenough"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "newname"
    assert response.json()["email"] == "new@example.com"


# ── TaskCreate ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
def test_create_task_accepts_valid_status(client, user_headers, status):
    response = client.post("/tasks/", json={"title": "t", "status": status}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["status"] == status


@pytest.mark.parametrize("status", ["invalid", "DONE", "in progress", "", None])
def test_create_task_rejects_invalid_status(client, user_headers, status):
    response = client.post("/tasks/", json={"title": "t", "status": status}, headers=user_headers)

    assert _errors_for(response, "status")


def test_invalid_status_error_lists_allowed_values(client, user_headers):
    response = client.post("/tasks/", json={"title": "t", "status": "blocked"}, headers=user_headers)

    msg = _errors_for(response, "status")[0]
    assert "todo" in msg and "in_progress" in msg and "done" in msg and "blocked" in msg


@pytest.mark.parametrize("priority", [1, 2, 3])
def test_create_task_accepts_valid_priority(client, user_headers, priority):
    response = client.post("/tasks/", json={"title": "t", "priority": priority}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["priority"] == priority


@pytest.mark.parametrize("priority", [0, 4, -1, 99, None, "high"])
def test_create_task_rejects_invalid_priority(client, user_headers, priority):
    response = client.post("/tasks/", json={"title": "t", "priority": priority}, headers=user_headers)

    assert _errors_for(response, "priority")


def test_invalid_priority_error_is_descriptive(client, user_headers):
    response = client.post("/tasks/", json={"title": "t", "priority": 99}, headers=user_headers)

    msg = _errors_for(response, "priority")[0]
    assert "[1, 2, 3]" in msg and "99" in msg


@pytest.mark.parametrize("title", ["x", "A normal title", "y" * 200])
def test_create_task_accepts_valid_title(client, user_headers, title):
    assert client.post("/tasks/", json={"title": title}, headers=user_headers).status_code == 200


@pytest.mark.parametrize("title", ["", "   ", "z" * 201])
def test_create_task_rejects_invalid_title(client, user_headers, title):
    response = client.post("/tasks/", json={"title": title}, headers=user_headers)

    assert _errors_for(response, "title")


def test_create_task_requires_title(client, user_headers):
    response = client.post("/tasks/", json={"priority": 1}, headers=user_headers)

    assert _errors_for(response, "title") == ["Field required"]


# ── TaskUpdate ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payload, field", [
    ({"status": "archived"}, "status"),
    ({"priority": 5}, "priority"),
    ({"title": ""}, "title"),
    ({"title": None}, "title"),
    ({"status": None}, "status"),
    ({"priority": None}, "priority"),
])
def test_update_task_rejects_invalid_values(client, user_headers, task, payload, field):
    response = client.put(f"/tasks/{task['id']}", json=payload, headers=user_headers)

    assert _errors_for(response, field)
    # Nothing was changed
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).json() == task


def test_update_task_accepts_valid_values(client, user_headers, task):
    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "Renamed", "status": "done", "priority": 3},
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["status"], body["priority"]) == ("Renamed", "done", 3)


def test_update_task_partial_payload_leaves_other_fields(client, user_headers, task):
    response = client.put(f"/tasks/{task['id']}", json={"description": None}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["description"] is None      # nullable field may be cleared
    assert response.json()["status"] == task["status"]
