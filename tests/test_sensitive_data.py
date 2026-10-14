# tests/test_sensitive_data.py

"""
UC-2: password hashes must never appear in API responses.
"""

from app.schemas import UserOut


def test_user_schema_has_no_credentials():
    assert "password_hash" not in UserOut.model_fields
    assert "password" not in UserOut.model_fields


def test_register_response_has_no_password_hash(client):
    response = client.post("/auth/register", json={
        "username": "fresh", "email": "fresh@example.com", "password": "fresh-pass1",
    })

    assert response.status_code == 200
    assert "password_hash" not in response.json()


def test_users_me_has_no_password_hash(client, user_headers):
    response = client.get("/users/me", headers=user_headers)

    assert response.status_code == 200
    assert "password_hash" not in response.json()


def test_users_list_has_no_password_hash(client, user, other_user, user_headers):
    response = client.get("/users/", headers=user_headers)

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all("password_hash" not in u for u in response.json())


def test_get_user_has_no_password_hash(client, other_user, user_headers):
    response = client.get(f"/users/{other_user.id}", headers=user_headers)

    assert response.status_code == 200
    assert "password_hash" not in response.json()


def test_update_user_has_no_password_hash(client, user, user_headers):
    response = client.put(
        f"/users/{user.id}", json={"password": "new-password1"}, headers=user_headers,
    )

    assert response.status_code == 200
    assert "password_hash" not in response.json()


def test_openapi_schema_does_not_advertise_password_hash(client):
    user_out = client.get("/openapi.json").json()["components"]["schemas"]["UserOut"]

    assert "password_hash" not in user_out["properties"]
