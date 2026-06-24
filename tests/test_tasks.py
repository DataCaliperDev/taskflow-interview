from app.models import Task


def test_create_list_update_and_delete_own_task(client, auth_headers):
    headers, _ = auth_headers()

    create_response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers=headers,
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["id"]

    list_response = client.get("/tasks/", headers=headers)
    assert list_response.status_code == 200
    assert any(task["id"] == task_id for task in list_response.json())

    update_response = client.put(
        f"/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "in_progress"

    delete_response = client.delete(f"/tasks/{task_id}", headers=headers)
    assert delete_response.status_code == 200

    get_response = client.get(f"/tasks/{task_id}", headers=headers)
    assert get_response.status_code == 404


def test_member_cannot_update_or_delete_another_users_task(
    client, db_session, auth_headers
):
    owner_headers, owner = auth_headers(username="owner")
    other_headers, _ = auth_headers(username="other")
    task = Task(title="Private task", owner_id=owner.id)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    update_response = client.put(
        f"/tasks/{task.id}",
        json={"status": "done"},
        headers=other_headers,
    )
    delete_response = client.delete(f"/tasks/{task.id}", headers=other_headers)

    assert update_response.status_code == 403
    assert delete_response.status_code == 403
    assert client.get(f"/tasks/{task.id}", headers=owner_headers).status_code == 200


def test_admin_can_update_and_delete_any_task(client, db_session, auth_headers):
    _, owner = auth_headers(username="owner")
    admin_headers, _ = auth_headers(username="admin", role="admin")
    task = Task(title="Admin managed task", owner_id=owner.id)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    update_response = client.put(
        f"/tasks/{task.id}",
        json={"priority": 3},
        headers=admin_headers,
    )
    delete_response = client.delete(f"/tasks/{task.id}", headers=admin_headers)

    assert update_response.status_code == 200
    assert update_response.json()["priority"] == 3
    assert delete_response.status_code == 200


def test_task_validation_rejects_invalid_status_priority_and_title(client, auth_headers):
    headers, _ = auth_headers()

    invalid_payloads = [
        {"title": "", "priority": 2, "status": "todo"},
        {"title": "Bad status", "priority": 2, "status": "blocked"},
        {"title": "Bad priority", "priority": 99, "status": "todo"},
    ]

    for payload in invalid_payloads:
        response = client.post("/tasks/", json=payload, headers=headers)
        assert response.status_code == 422


def test_task_update_validation_rejects_invalid_status_priority_and_title(
    client, db_session, auth_headers
):
    headers, user = auth_headers()
    task = Task(title="Valid task", owner_id=user.id)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    invalid_payloads = [
        {"title": ""},
        {"status": "blocked"},
        {"priority": 0},
    ]

    for payload in invalid_payloads:
        response = client.put(f"/tasks/{task.id}", json=payload, headers=headers)
        assert response.status_code == 422
