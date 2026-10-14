# tests/test_tasks.py

"""
Tests for the /tasks endpoints.
"""


def test_create_task(client, user, user_headers):
    response = client.post(
        "/tasks/",
        json={"title": "Test Task", "priority": 3, "status": "in_progress",
              "tags": "backend,api"},
        headers=user_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["id"], int)
    assert data["title"] == "Test Task"
    assert data["priority"] == 3
    assert data["status"] == "in_progress"
    assert data["tags"] == "backend,api"
    assert data["description"] is None
    assert data["owner_id"] == user.id
    assert data["comments"] == []


def test_create_task_defaults(client, user_headers):
    response = client.post("/tasks/", json={"title": "Minimal"}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "todo"
    assert response.json()["priority"] == 2


def test_create_task_requires_auth(client):
    response = client.post("/tasks/", json={"title": "Sneaky"})

    assert response.status_code == 401


def test_list_tasks(client, user_headers, task):
    response = client.get("/tasks/", headers=user_headers)

    assert response.status_code == 200
    tasks = response.json()
    assert [t["id"] for t in tasks] == [task["id"]]
    assert tasks[0]["title"] == "Write report"


def test_list_tasks_filters(client, user, user_headers, other_headers, make_task):
    mine_todo = make_task(user_headers, title="mine todo", status="todo")
    make_task(user_headers, title="mine done", status="done")
    make_task(other_headers, title="theirs todo", status="todo")

    response = client.get(
        "/tasks/", params={"status": "todo", "owner_id": user.id}, headers=user_headers,
    )

    assert response.status_code == 200
    assert [t["id"] for t in response.json()] == [mine_todo["id"]]


def test_get_task(client, user_headers, task):
    response = client.get(f"/tasks/{task['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json() == task


def test_get_missing_task(client, user_headers):
    response = client.get("/tasks/9999", headers=user_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task(client, user_headers, task):
    response = client.put(
        f"/tasks/{task['id']}", json={"status": "in_progress"}, headers=user_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["title"] == task["title"]          # untouched fields preserved
    assert data["priority"] == task["priority"]
    # And the change is persisted
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).json()["status"] == "in_progress"


def test_delete_task(client, user_headers, task):
    response = client.delete(f"/tasks/{task['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json() == {"message": "Task deleted"}
    assert client.get(f"/tasks/{task['id']}", headers=user_headers).status_code == 404


def test_search_tasks(client, user_headers, make_task):
    hit = make_task(user_headers, title="Fix login bug")
    make_task(user_headers, title="Write docs")

    response = client.get("/tasks/search", params={"q": "login"}, headers=user_headers)

    assert response.status_code == 200
    results = response.json()
    assert [r["id"] for r in results] == [hit["id"]]
    assert results[0]["title"] == "Fix login bug"


def test_search_tasks_no_match(client, user_headers, task):
    response = client.get("/tasks/search", params={"q": "nothing-matches"}, headers=user_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_add_comment(client, other_user, other_headers, user_headers, task):
    response = client.post(
        f"/tasks/{task['id']}/comments", json={"content": "Looks good"}, headers=other_headers,
    )

    assert response.status_code == 200
    comment = response.json()
    assert comment["content"] == "Looks good"
    assert comment["author_id"] == other_user.id
    # Comment is visible on the task
    comments = client.get(f"/tasks/{task['id']}", headers=user_headers).json()["comments"]
    assert [c["id"] for c in comments] == [comment["id"]]


def test_add_comment_to_missing_task(client, user_headers):
    response = client.post("/tasks/9999/comments", json={"content": "?"}, headers=user_headers)

    assert response.status_code == 404


def test_get_task_tags(client, user_headers, make_task):
    task = make_task(user_headers, tags="frontend,urgent")

    response = client.get(f"/tasks/{task['id']}/tags", headers=user_headers)

    assert response.status_code == 200
    assert response.json() == {"tags": ["frontend", "urgent"]}


def test_task_summary_by_user(client, user, other_user, user_headers, make_task):
    make_task(user_headers, priority=3, status="todo")        # score 30
    make_task(user_headers, priority=1, status="in_progress")  # score 15

    response = client.get("/tasks/summary/by-user", headers=user_headers)

    assert response.status_code == 200
    summary = {row["username"]: row for row in response.json()}
    assert summary[user.username]["task_count"] == 2
    assert summary[user.username]["avg_priority_score"] == 22.5
    assert summary[other_user.username]["task_count"] == 0
    assert summary[other_user.username]["avg_priority_score"] == 0
