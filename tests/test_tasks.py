# tests/test_tasks.py

"""
Tests for the /tasks endpoints.

Each test builds the data it needs through the make_task factory. The suite
previously chained six tests through a module-level created_task_id, so deleting
the first one broke the other five.
"""

import pytest

from app import models


# ── CRUD ─────────────────────────────────────────────────────────────────────


def test_create_task(client, make_user):
    user, auth = make_user("owner")

    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 2, "status": "todo"},
        headers=auth,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Test Task"
    assert body["priority"] == 2
    assert body["status"] == "todo"
    assert body["owner_id"] == user["id"]
    assert body["comments"] == []
    assert isinstance(body["id"], int)


def test_list_tasks_contains_the_created_task(client, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth, title="Findable")

    response = client.get("/tasks/", headers=auth)

    assert response.status_code == 200
    titles = {t["title"]: t for t in response.json()}
    assert "Findable" in titles
    assert titles["Findable"]["id"] == task["id"]


def test_get_task_returns_the_stored_fields(client, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth, title="Readable", priority=3, status="in_progress")

    response = client.get(f"/tasks/{task['id']}", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == task["id"]
    assert body["title"] == "Readable"
    assert body["priority"] == 3
    assert body["status"] == "in_progress"


def test_update_task_changes_only_the_submitted_fields(client, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth, title="Original", priority=1, status="todo")

    response = client.put(
        f"/tasks/{task['id']}", json={"status": "in_progress"}, headers=auth,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    # The untouched fields are the point: a handler assigning the whole payload
    # would blank these and still answer 200.
    assert body["title"] == "Original"
    assert body["priority"] == 1


def test_delete_task_removes_it(client, db_session, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth)

    response = client.delete(f"/tasks/{task['id']}", headers=auth)

    assert response.status_code == 200
    assert response.json() == {"message": "Task deleted"}
    assert db_session.query(models.Task).filter(
        models.Task.id == task["id"]
    ).first() is None


def test_get_deleted_task(client, make_user, make_task):
    """A deleted task is gone from the API too, not only from the database.

    Self-contained now: the original relied on test_delete_task having already
    run and left its id in a module-level variable.
    """
    _, auth = make_user("owner")
    task = make_task(auth)
    client.delete(f"/tasks/{task['id']}", headers=auth)

    response = client.get(f"/tasks/{task['id']}", headers=auth)

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


# ── Must have: unauthenticated access ────────────────────────────────────────


@pytest.mark.parametrize("method, path, kwargs", [
    ("get", "/tasks/", {}),
    ("get", "/tasks/1", {}),
    ("post", "/tasks/", {"json": {"title": "x"}}),
    ("put", "/tasks/1", {"json": {"title": "x"}}),
    ("delete", "/tasks/1", {}),
    ("get", "/tasks/search", {"params": {"q": "x"}}),
    ("get", "/tasks/summary/by-user", {}),
])
def test_task_routes_require_authentication(client, method, path, kwargs):
    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_a_malformed_token_is_rejected(client):
    response = client.get(
        "/tasks/", headers={"Authorization": "Bearer not-a-real-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


# ── Must have: invalid input ─────────────────────────────────────────────────


def test_creating_a_task_without_a_title_is_rejected(client, make_user):
    _, auth = make_user("owner")

    response = client.post("/tasks/", json={"priority": 2}, headers=auth)

    assert response.status_code == 422


def test_a_non_integer_priority_is_rejected(client, make_user):
    _, auth = make_user("owner")

    response = client.post(
        "/tasks/", json={"title": "x", "priority": "high"}, headers=auth,
    )

    assert response.status_code == 422


def test_operations_on_a_missing_task_return_404(client, make_user):
    _, auth = make_user("owner")

    assert client.get("/tasks/999999", headers=auth).status_code == 404
    assert client.put(
        "/tasks/999999", json={"title": "x"}, headers=auth,
    ).status_code == 404
    assert client.delete("/tasks/999999", headers=auth).status_code == 404


@pytest.mark.xfail(
    reason="No validation on status or priority — TaskCreate accepts anything. "
           "Field-level validation belongs to a different use case.",
    strict=True,
)
def test_out_of_range_values_are_rejected(client, make_user):
    _, auth = make_user("owner")

    response = client.post(
        "/tasks/", json={"title": "x", "priority": 99, "status": "nonsense"},
        headers=auth,
    )
    assert response.status_code == 422


# ── Must have: search ────────────────────────────────────────────────────────


def test_search_finds_tasks_by_title(client, make_user, make_task):
    _, auth = make_user("owner")
    make_task(auth, title="Deploy the pipeline")
    make_task(auth, title="Write documentation")

    response = client.get("/tasks/search", params={"q": "pipeline"}, headers=auth)

    assert response.status_code == 200
    titles = [row["title"] for row in response.json()]
    assert titles == ["Deploy the pipeline"]


def test_search_returns_an_empty_list_when_nothing_matches(client, make_user, make_task):
    _, auth = make_user("owner")
    make_task(auth, title="Deploy the pipeline")

    response = client.get("/tasks/search", params={"q": "zzzzz"}, headers=auth)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.xfail(
    reason="tasks.py builds the search SQL by string interpolation. A quote is a "
           "syntax error and a crafted term returns every row. Fixing it means "
           "bound parameters, which belongs to the SQL-injection use case.",
    strict=True,
)
def test_search_treats_the_query_as_data_not_sql(client, make_user, make_task):
    """Documents a verified injection rather than leaving it in prose.

    strict=True means this reports XPASS the moment someone parameterises the
    query, which is the reminder to delete the marker.
    """
    _, auth = make_user("owner")
    make_task(auth, title="Deploy the pipeline")
    make_task(auth, title="Write documentation")

    quoted = client.get(
        "/tasks/search", params={"q": "O'Brien"}, headers=auth,
    )
    assert quoted.status_code == 200

    injected = client.get(
        "/tasks/search", params={"q": "' OR '1'='1"}, headers=auth,
    )
    assert injected.json() == []


# ── Must have: comments ──────────────────────────────────────────────────────


def test_adding_a_comment_returns_it(client, make_user, make_task):
    user, auth = make_user("owner")
    task = make_task(auth)

    response = client.post(
        f"/tasks/{task['id']}/comments",
        json={"content": "Blocked on secrets config"},
        headers=auth,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Blocked on secrets config"
    assert body["author_id"] == user["id"]
    assert isinstance(body["id"], int)


def test_comments_are_returned_with_the_task(client, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth)
    client.post(
        f"/tasks/{task['id']}/comments", json={"content": "first"}, headers=auth,
    )
    client.post(
        f"/tasks/{task['id']}/comments", json={"content": "second"}, headers=auth,
    )

    body = client.get(f"/tasks/{task['id']}", headers=auth).json()

    assert [c["content"] for c in body["comments"]] == ["first", "second"]


def test_commenting_on_a_missing_task_returns_404(client, make_user):
    _, auth = make_user("owner")

    response = client.post(
        "/tasks/999999/comments", json={"content": "x"}, headers=auth,
    )

    assert response.status_code == 404


def test_anyone_authenticated_may_comment_on_a_task(client, make_user, make_task):
    """Current behaviour, asserted so a future ownership rule is a visible change.

    UC-3 restricted editing and deleting a task to its owner; commenting was
    left open, which is reasonable for a collaboration tool but was never
    stated anywhere.
    """
    _, owner_auth = make_user("owner")
    other, other_auth = make_user("other")
    task = make_task(owner_auth)

    response = client.post(
        f"/tasks/{task['id']}/comments", json={"content": "drive-by"},
        headers=other_auth,
    )

    assert response.status_code == 200
    assert response.json()["author_id"] == other["id"]


# ── Nice to have ─────────────────────────────────────────────────────────────


def test_tags_are_split_on_commas(client, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth, tags="devops,infra")

    response = client.get(f"/tasks/{task['id']}/tags", headers=auth)

    assert response.status_code == 200
    assert response.json() == {"tags": ["devops", "infra"]}


def test_a_task_without_tags_returns_an_empty_list(client, make_user, make_task):
    _, auth = make_user("owner")
    task = make_task(auth)

    response = client.get(f"/tasks/{task['id']}/tags", headers=auth)

    assert response.json() == {"tags": []}


def test_listing_tasks_can_be_filtered_by_status(client, make_user, make_task):
    _, auth = make_user("owner")
    make_task(auth, title="Open", status="todo")
    make_task(auth, title="Finished", status="done")

    response = client.get("/tasks/", params={"status": "done"}, headers=auth)

    assert [t["title"] for t in response.json()] == ["Finished"]


def test_listing_tasks_can_be_filtered_by_owner(client, make_user, make_task):
    owner, owner_auth = make_user("owner")
    _, other_auth = make_user("other")
    make_task(owner_auth, title="Mine")
    make_task(other_auth, title="Theirs")

    response = client.get(
        "/tasks/", params={"owner_id": owner["id"]}, headers=owner_auth,
    )

    assert [t["title"] for t in response.json()] == ["Mine"]


def test_listing_tasks_returns_every_owner(client, make_user, make_task):
    """Asserted because it is load-bearing elsewhere: UC-3 left task reads open
    precisely because this list already shows the frontend everyone's tasks."""
    _, owner_auth = make_user("owner")
    _, other_auth = make_user("other")
    make_task(owner_auth, title="Mine")
    make_task(other_auth, title="Theirs")

    titles = {t["title"] for t in client.get("/tasks/", headers=owner_auth).json()}

    assert titles == {"Mine", "Theirs"}


def test_health_check_is_open(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
