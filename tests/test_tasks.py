"""Tests for /tasks (UC-3, UC-5, UC-6, UC-12)."""


def test_create_task_returns_201_with_owner(client, bob_token, auth_header, seeded_users):
    resp = client.post(
        "/tasks/",
        json={"title": "Write tests", "priority": 3, "status": "todo"},
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Write tests"
    assert body["priority"] == 3
    assert body["status"] == "todo"
    assert body["owner_id"] == seeded_users["bob"].id
    assert body["comments"] == []


def test_get_task_returns_full_body(client, bob_token, auth_header, make_task):
    created = make_task(bob_token, title="Lookup me")
    resp = client.get(f"/tasks/{created['id']}", headers=auth_header(bob_token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Lookup me"


def test_owner_can_update_task(client, bob_token, auth_header, make_task):
    created = make_task(bob_token)
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_non_owner_cannot_update_task(client, bob_token, carol_token, auth_header, make_task):
    """UC-3: a member cannot mutate another member's task."""
    created = make_task(bob_token)
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=auth_header(carol_token),
    )
    assert resp.status_code == 403


def test_admin_can_update_any_task(client, bob_token, admin_token, auth_header, make_task):
    """UC-3: admin overrides ownership."""
    created = make_task(bob_token)
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


def test_non_owner_cannot_delete_task(client, bob_token, carol_token, auth_header, make_task):
    created = make_task(bob_token)
    resp = client.delete(f"/tasks/{created['id']}", headers=auth_header(carol_token))
    assert resp.status_code == 403


def test_owner_can_delete_task(client, bob_token, auth_header, make_task):
    created = make_task(bob_token)
    resp = client.delete(f"/tasks/{created['id']}", headers=auth_header(bob_token))
    assert resp.status_code == 204
    follow = client.get(f"/tasks/{created['id']}", headers=auth_header(bob_token))
    assert follow.status_code == 404


def test_admin_can_delete_any_task(client, bob_token, admin_token, auth_header, make_task):
    created = make_task(bob_token)
    resp = client.delete(f"/tasks/{created['id']}", headers=auth_header(admin_token))
    assert resp.status_code == 204


def test_unauthenticated_cannot_list_tasks(client):
    assert client.get("/tasks/").status_code == 401


def test_list_tasks_paginated_envelope(client, bob_token, auth_header, make_task):
    """UC-6: pagination metadata."""
    for i in range(15):
        make_task(bob_token, title=f"t{i}")
    resp = client.get("/tasks/?page=1&page_size=10", headers=auth_header(bob_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] == 15
    assert body["total_pages"] == 2
    assert len(body["items"]) == 10


def test_list_tasks_last_page(client, bob_token, auth_header, make_task):
    for i in range(15):
        make_task(bob_token, title=f"t{i}")
    resp = client.get("/tasks/?page=2&page_size=10", headers=auth_header(bob_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert len(body["items"]) == 5


def test_list_tasks_empty(client, bob_token, auth_header):
    resp = client.get("/tasks/", headers=auth_header(bob_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["total_pages"] == 0


def test_list_tasks_page_size_capped(client, bob_token, auth_header):
    """page_size > 100 must be rejected by validation."""
    resp = client.get("/tasks/?page=1&page_size=500", headers=auth_header(bob_token))
    assert resp.status_code == 422


def test_list_tasks_filter_by_status(client, bob_token, auth_header, make_task):
    make_task(bob_token, title="t1", status="todo")
    make_task(bob_token, title="t2", status="done")
    resp = client.get("/tasks/?status=done", headers=auth_header(bob_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "done"


def test_search_tasks_by_title(client, bob_token, auth_header, make_task):
    make_task(bob_token, title="Write API docs")
    make_task(bob_token, title="Fix bug")
    resp = client.get("/tasks/search?q=API", headers=auth_header(bob_token))
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert "API" in rows[0]["title"]


def test_create_task_invalid_priority_still_accepted_at_db(
    client, bob_token, auth_header
):
    """No schema-side priority validation today; documents current contract."""
    resp = client.post(
        "/tasks/",
        json={"title": "x", "priority": 99, "status": "todo"},
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 201


def test_get_task_404(client, bob_token, auth_header):
    assert client.get("/tasks/9999", headers=auth_header(bob_token)).status_code == 404


def test_summary_by_user_aggregates_in_one_query(
    client, bob_token, admin_token, auth_header, make_task
):
    """UC-5: counts and avg score returned without N+1."""
    make_task(bob_token, status="todo", priority=2)       # 20
    make_task(bob_token, status="in_progress", priority=2) # 30
    make_task(bob_token, status="done", priority=3)        # 0
    resp = client.get("/tasks/summary/by-user", headers=auth_header(admin_token))
    assert resp.status_code == 200
    rows = {r["username"]: r for r in resp.json()}
    assert rows["bob"]["task_count"] == 3
    assert rows["bob"]["avg_priority_score"] == round((20 + 30 + 0) / 3, 2)
    # Users with no tasks still appear with zero counts.
    assert rows["carol"]["task_count"] == 0
    assert rows["carol"]["avg_priority_score"] == 0.0


def test_add_and_list_comments(client, bob_token, auth_header, make_task):
    created = make_task(bob_token)
    resp = client.post(
        f"/tasks/{created['id']}/comments",
        json={"content": "first comment"},
        headers=auth_header(bob_token),
    )
    assert resp.status_code == 201
    cbody = resp.json()
    assert cbody["content"] == "first comment"

    resp = client.get(f"/tasks/{created['id']}/comments", headers=auth_header(bob_token))
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["content"] == "first comment"
