# tests/test_users.py

"""
Tests for the /users endpoints.
"""

import pytest

from app import models
from app.schemas import MASKED_PASSWORD_HASH


def _register(client, prefix="extra"):
    """Register one more user, for cases that need a registration response."""
    return client.post("/auth/register", json={
        "username": prefix,
        "email": f"{prefix}@example.com",
        "password": "test-password",
    })


def _user_objects(response):
    """Every user object in a response body, whether it is a list or a single."""
    body = response.json()
    return body if isinstance(body, list) else [body]


def test_get_me_returns_the_authenticated_user(client, make_user):
    user, auth = make_user("me")

    response = client.get("/users/me", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user["id"]
    assert body["username"] == user["username"]
    assert body["email"] == f"{user['username']}@example.com"
    assert body["role"] == "member"
    assert body["is_active"] is True


def test_list_users_returns_every_account(client, make_user):
    first, auth = make_user("first")
    second, _ = make_user("second")

    response = client.get("/users/", headers=auth)

    assert response.status_code == 200
    ids = {u["id"] for u in response.json()}
    assert {first["id"], second["id"]} <= ids


def test_list_users_unauthenticated(client):
    response = client.get("/users/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_update_user_applies_the_change(client, db_session, make_user):
    user, auth = make_user("target")

    response = client.put(
        f"/users/{user['id']}", json={"username": "renamed"}, headers=auth,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "renamed"

    # Confirm it reached the database, not just the response model.
    stored = db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first()
    assert stored.username == "renamed"


def test_update_user_leaves_unsubmitted_fields_alone(client, make_user):
    user, auth = make_user("target")
    original_email = f"{user['username']}@example.com"

    body = client.put(
        f"/users/{user['id']}", json={"username": "renamed"}, headers=auth,
    ).json()

    assert body["email"] == original_email
    assert body["role"] == "member"


def test_get_user_by_id(client, make_user):
    target, _ = make_user("target")
    _, auth = make_user("viewer")

    response = client.get(f"/users/{target['id']}", headers=auth)

    assert response.status_code == 200
    assert response.json()["username"] == target["username"]


def test_operations_on_a_missing_user_return_404(client, make_user):
    _, auth = make_user("viewer")

    assert client.get("/users/999999", headers=auth).status_code == 404
    assert client.put(
        "/users/999999", json={"username": "x"}, headers=auth,
    ).status_code == 404
    assert client.delete("/users/999999", headers=auth).status_code == 404


# ── /users/{id}/tasks ────────────────────────────────────────────────────────


def test_user_tasks_returns_only_that_users_tasks(client, make_user, make_task):
    owner, owner_auth = make_user("owner")
    other, other_auth = make_user("other")
    make_task(owner_auth, title="Mine")
    make_task(other_auth, title="Theirs")

    response = client.get(f"/users/{owner['id']}/tasks", headers=owner_auth)

    assert response.status_code == 200
    assert [t["title"] for t in response.json()] == ["Mine"]


def test_user_tasks_is_empty_for_a_user_with_none(client, make_user):
    user, auth = make_user("idle")

    response = client.get(f"/users/{user['id']}/tasks", headers=auth)

    assert response.status_code == 200
    assert response.json() == []


def test_user_tasks_for_a_missing_user_returns_404(client, make_user):
    _, auth = make_user("viewer")

    assert client.get("/users/999999/tasks", headers=auth).status_code == 404


@pytest.mark.parametrize("method, path, kwargs", [
    ("get", "/users/", {}),
    ("get", "/users/me", {}),
    ("get", "/users/1", {}),
    ("put", "/users/1", {"json": {"username": "x"}}),
    ("delete", "/users/1", {}),
    ("get", "/users/1/tasks", {}),
])
def test_user_routes_require_authentication(client, method, path, kwargs):
    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ── UC-2 · password hash exposure ────────────────────────────────────────────


def _all_user_responses(client, db_session, make_user):
    """Hit every route that returns a user object, plus the stored hash.

    Returns (responses_by_name, real_hash) so a test can compare what the API
    emitted against what is actually in the database.
    """
    user, auth = make_user("subject")
    real_hash = db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first().password_hash

    return {
        "POST /auth/register": _register(client, "registered"),
        "GET /users/me": client.get("/users/me", headers=auth),
        "GET /users/": client.get("/users/", headers=auth),
        "GET /users/{id}": client.get(f"/users/{user['id']}", headers=auth),
        "PUT /users/{id}": client.put(
            f"/users/{user['id']}", json={"username": "renamed"}, headers=auth,
        ),
    }, real_hash


def test_stored_password_hash_never_appears_in_any_user_response(
    client, db_session, make_user,
):
    """The security assertion: the real hash does not reach the wire.

    Compares against the raw response text rather than a parsed field, so it
    holds no matter how the masking is implemented or which key it hides behind.
    """
    responses, real_hash = _all_user_responses(client, db_session, make_user)

    # Guard the test itself: a blank or already-masked hash would make the
    # assertions below pass for the wrong reason.
    assert real_hash.startswith("$2b$")

    for name, response in responses.items():
        assert response.status_code == 200, name
        assert real_hash not in response.text, name


@pytest.mark.parametrize("endpoint", [
    "POST /auth/register",
    "GET /users/me",
    "GET /users/",
    "GET /users/{id}",
    "PUT /users/{id}",
])
def test_password_hash_is_masked_on_every_user_endpoint(
    client, db_session, make_user, endpoint,
):
    """Consistency: the fix is in the schema, so all five routes behave alike."""
    responses, _ = _all_user_responses(client, db_session, make_user)
    response = responses[endpoint]

    users = _user_objects(response)
    assert users, f"{endpoint} returned no user object"
    for user in users:
        assert user["password_hash"] == MASKED_PASSWORD_HASH


def test_masking_is_not_bypassed_by_a_real_stored_hash(client, db_session, make_user):
    """A row holding a genuine bcrypt hash still serialises to the placeholder.

    Without this, the masking tests would also pass against an empty column.
    """
    user, auth = make_user("subject")
    stored = db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first()
    assert stored.password_hash.startswith("$2b$")

    response = client.get("/users/me", headers=auth)
    assert response.json()["password_hash"] == MASKED_PASSWORD_HASH


def test_masking_does_not_drop_the_other_user_fields(client, make_user):
    """Guards against over-removal: a schema stripped too far would otherwise
    satisfy every assertion above."""
    user, auth = make_user("subject")
    body = client.get("/users/me", headers=auth).json()

    for field in ("id", "username", "email", "role", "is_active", "created_at"):
        assert field in body, field
    assert body["username"] == user["username"]
    assert body["role"] == "member"
    assert body["is_active"] is True


def test_password_hash_is_marked_deprecated_in_the_openapi_schema(client):
    """The published contract has to say the field is going away, not just
    return a placeholder — otherwise consumers have no signal to migrate."""
    schema = client.get("/openapi.json").json()
    field = schema["components"]["schemas"]["UserOut"]["properties"]["password_hash"]

    assert field.get("deprecated") is True
    assert "***" in field.get("description", "")
