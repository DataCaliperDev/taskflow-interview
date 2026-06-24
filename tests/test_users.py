def test_get_me_hides_password_hash(client, auth_headers):
    headers, _ = auth_headers()

    response = client.get("/users/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    assert "password_hash" not in data


def test_list_users_hides_password_hash(client, auth_headers, make_user):
    headers, _ = auth_headers()
    make_user(username="other")

    response = client.get("/users/", headers=headers)

    assert response.status_code == 200
    assert response.json()
    assert all("password_hash" not in user for user in response.json())


def test_list_users_unauthenticated(client):
    response = client.get("/users/")

    assert response.status_code == 401


def test_user_can_update_own_profile(client, auth_headers):
    headers, user = auth_headers()

    response = client.put(
        f"/users/{user.id}",
        json={"username": "updateduser"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "updateduser"
    assert "password_hash" not in response.json()


def test_member_cannot_update_another_user(client, auth_headers):
    headers, _ = auth_headers(username="member")
    _, other = auth_headers(username="other")

    response = client.put(
        f"/users/{other.id}",
        json={"username": "blockedupdate"},
        headers=headers,
    )

    assert response.status_code == 403


def test_member_cannot_delete_another_user_with_admin_override_header(
    client, auth_headers
):
    headers, _ = auth_headers(username="member")
    _, other = auth_headers(username="other")
    headers_with_override = {**headers, "X-Admin-Override": "admin-secret-2024"}

    response = client.delete(f"/users/{other.id}", headers=headers_with_override)

    assert response.status_code == 403


def test_admin_can_delete_another_user(client, auth_headers):
    admin_headers, _ = auth_headers(username="admin", role="admin")
    _, other = auth_headers(username="other")

    response = client.delete(f"/users/{other.id}", headers=admin_headers)

    assert response.status_code == 200
