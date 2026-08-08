# tests/test_users.py

"""
Tests for the /users endpoints.
"""

import uuid

import pytest

from app import models
from app.schemas import MASKED_PASSWORD_HASH

PASSWORD = "uc2-test-password"


def _register(client, prefix):
    """Register a fresh user; returns the response.

    Names are generated per run because the suite keeps an on-disk test.db that
    is never reset (UC-12's scope).
    """
    username = f"{prefix}-{uuid.uuid4().hex[:8]}"
    return client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD,
    })


def _register_and_login(client, prefix):
    """Return (user_body, auth_header) for a newly created user."""
    user = _register(client, prefix).json()
    token = client.post("/auth/login", data={
        "username": user["username"],
        "password": PASSWORD,
    }).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def _user_objects(response):
    """Every user object in a response body, whether it is a list or a single."""
    body = response.json()
    return body if isinstance(body, list) else [body]


def test_get_me(client, test_user_token):
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    # Issue: does not assert that password_hash is NOT in the response


def test_list_users_authenticated(client, test_user_token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200


def test_list_users_unauthenticated(client):
    response = client.get("/users/")
    # Issue: test expects 401, which is correct — but it only checks the code, not the error message
    assert response.status_code == 401


def test_update_user(client, test_user_token):
    # First get our own id
    me = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"},
    ).json()

    response = client.put(
        f"/users/{me['id']}",
        json={"username": "updateduser"},
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    assert response.status_code == 200
    # Issue: no assertion that username was actually changed to "updateduser"


# Issue: no test verifying that a normal user CANNOT update another user's profile
# Issue: no test for the admin override header on DELETE
# Issue: no test for get_user_tasks


# ── UC-2 · password hash exposure ────────────────────────────────────────────


def _all_user_responses(client, db_session):
    """Hit every route that returns a user object, plus the stored hash.

    Returns (responses_by_name, real_hash) so a test can compare what the API
    emitted against what is actually in the database.
    """
    user, auth = _register_and_login(client, "uc2")
    real_hash = db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first().password_hash

    return {
        "POST /auth/register": _register(client, "uc2-reg"),
        "GET /users/me": client.get("/users/me", headers=auth),
        "GET /users/": client.get("/users/", headers=auth),
        "GET /users/{id}": client.get(f"/users/{user['id']}", headers=auth),
        "PUT /users/{id}": client.put(
            f"/users/{user['id']}",
            json={"username": f"renamed-{uuid.uuid4().hex[:8]}"},
            headers=auth,
        ),
    }, real_hash


def test_stored_password_hash_never_appears_in_any_user_response(client, db_session):
    """The security assertion: the real hash does not reach the wire.

    Compares against the raw response text rather than a parsed field, so it
    holds no matter how the masking is implemented or which key it hides behind.
    """
    responses, real_hash = _all_user_responses(client, db_session)

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
def test_password_hash_is_masked_on_every_user_endpoint(client, db_session, endpoint):
    """Consistency: the fix is in the schema, so all five routes behave alike."""
    responses, _ = _all_user_responses(client, db_session)
    response = responses[endpoint]

    users = _user_objects(response)
    assert users, f"{endpoint} returned no user object"
    for user in users:
        assert user["password_hash"] == MASKED_PASSWORD_HASH


def test_masking_is_not_bypassed_by_a_real_stored_hash(client, db_session):
    """A row holding a genuine bcrypt hash still serialises to the placeholder.

    Without this, the masking tests would also pass against an empty column.
    """
    user, auth = _register_and_login(client, "uc2-bypass")
    stored = db_session.query(models.User).filter(
        models.User.id == user["id"]
    ).first()
    assert stored.password_hash.startswith("$2b$")

    response = client.get("/users/me", headers=auth)
    assert response.json()["password_hash"] == MASKED_PASSWORD_HASH


def test_masking_does_not_drop_the_other_user_fields(client, db_session):
    """Guards against over-removal: a schema stripped too far would otherwise
    satisfy every assertion above."""
    user, auth = _register_and_login(client, "uc2-fields")
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
