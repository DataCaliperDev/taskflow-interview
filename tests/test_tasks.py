# tests/test_tasks.py

"""Tests for the /tasks endpoints."""


def _create(authed_client, **overrides):
    payload = {"title": "Sample", "priority": 2, "status": "todo", **overrides}
    return authed_client.post("/tasks/", json=payload)


# ── Validation (UC-9) ────────────────────────────────────────────────────────

def test_create_task_rejects_invalid_status(authed_client):
    response = _create(authed_client, status="banana")
    assert response.status_code == 422


def test_create_task_rejects_priority_out_of_range(authed_client):
    response = _create(authed_client, priority=99)
    assert response.status_code == 422


def test_create_task_rejects_empty_title(authed_client):
    response = _create(authed_client, title="")
    assert response.status_code == 422


def test_update_task_rejects_invalid_status(authed_client):
    created = _create(authed_client).json()
    response = authed_client.put(f"/tasks/{created['id']}", json={"status": "banana"})
    assert response.status_code == 422


# ── Pagination (UC-6) ────────────────────────────────────────────────────────

def test_list_tasks_returns_pagination_metadata(authed_client):
    for i in range(3):
        _create(authed_client, title=f"Task {i}")

    response = authed_client.get("/tasks/")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total_pages"] == 1
    assert len(body["items"]) == 3


def test_list_tasks_respects_page_and_page_size(authed_client):
    for i in range(15):
        _create(authed_client, title=f"Task {i}")

    page1 = authed_client.get("/tasks/?page=1&page_size=10").json()
    page2 = authed_client.get("/tasks/?page=2&page_size=10").json()

    assert page1["total"] == 15
    assert page1["total_pages"] == 2
    assert len(page1["items"]) == 10
    assert page2["page"] == 2
    assert len(page2["items"]) == 5

    page1_ids = {t["id"] for t in page1["items"]}
    page2_ids = {t["id"] for t in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_list_tasks_empty_returns_zero_metadata(authed_client):
    body = authed_client.get("/tasks/").json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 10, "total_pages": 0}


def test_list_tasks_page_size_over_max_rejected(authed_client):
    response = authed_client.get("/tasks/?page_size=101")
    assert response.status_code == 422


def test_user_tasks_paginated(authed_client):
    me = authed_client.get("/users/me").json()
    for i in range(12):
        _create(authed_client, title=f"Task {i}")

    body = authed_client.get(f"/users/{me['id']}/tasks?page=2&page_size=5").json()
    assert body["total"] == 12
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert body["total_pages"] == 3
    assert len(body["items"]) == 5
