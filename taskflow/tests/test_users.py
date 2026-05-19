# tests/test_users.py

"""
Tests for the /users endpoints.
"""


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
