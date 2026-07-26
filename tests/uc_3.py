# tests/uc_5.py

"""
Tests for the /tasks endpoints.
"""
from app.models import Task, User

# Issue: test depends on the order in which tests run (relies on task created by test_create_task)
# Issue: no fixture or factory — tests share state via module-level variables
created_task_id = None

# Test cases to check if admins can act on any task
def test_get_task_as_admin(client, db_session, test_admin_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Get the list of tasks owned by bob
    response = client.get(
        "/tasks/",
        params={"owner_id": bob.id},
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    bob_1st_task = response_content[0]

    # Get detail of the first task owned by bob
    response = client.get(
        f"/tasks/{bob_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )

    assert response.status_code == 200
    response_task = response.json()
    assert response_task["owner_id"] == bob.id


def test_update_task_as_admin(client, db_session, test_admin_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Get the list of tasks owned by bob
    response = client.get(
        "/tasks/",
        params={"owner_id": bob.id},
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    bob_1st_task = response_content[0]

    # Update the task as admin
    response = client.put(
        f"/tasks/{bob_1st_task['id']}",
        json={
            "title": "Updated by Admin",
            "status": "in_progress",
        },
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert response.status_code == 200
    task_from_db = db_session.query(Task).filter(Task.id == bob_1st_task['id']).first()
    assert task_from_db.title == "Updated by Admin"
    assert task_from_db.status == "in_progress"


def test_delete_task_as_admin(client, db_session, test_admin_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Get the list of tasks owned by bob
    response = client.get(
        "/tasks/",
        params={"owner_id": bob.id},
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    bob_1st_task = response_content[0]

    # Update the task as admin
    response = client.delete(
        f"/tasks/{bob_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )
    assert response.status_code == 204
    task_from_db = db_session.query(Task).filter(Task.id == bob_1st_task['id']).first()
    assert task_from_db is None

# Test cases to check if a user can update or delete their own tasks
def test_member_get_their_own_task(client, db_session, test_bob_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Get the list of tasks owned by bob
    response = client.get(
        "/tasks/",
        params={"owner_id": bob.id},
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    bob_1st_task = response_content[0]

    # Get detail of the first task owned by carol
    response = client.get(
        f"/tasks/{bob_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["owner_id"] == bob.id



def test_member_update_their_own_task(client, db_session, test_bob_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Get the list of tasks owned by bob
    response = client.get(
        "/tasks/",
        params={"owner_id": bob.id},
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    bob_1st_task = response_content[0]

    # Get detail of the first task owned by carol
    response = client.get(
        f"/tasks/{bob_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )
    response = client.put(
        f"/tasks/{bob_1st_task['id']}",
        json={
            "title": "Updated by Bob",
            "status": "in_progress",
        },
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    task_from_db = db_session.query(Task).filter(Task.id == bob_1st_task['id']).first()
    assert task_from_db.title == "Updated by Bob"
    assert task_from_db.status == "in_progress"


def test_member_delete_their_own_task(client, db_session, test_bob_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Get the list of tasks owned by bob
    response = client.get(
        "/tasks/",
        params={"owner_id": bob.id},
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    bob_1st_task = response_content[0]

    # Get detail of the first task owned by carol
    response = client.get(
        f"/tasks/{bob_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )
    response = client.delete(
        f"/tasks/{bob_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 204


# Test cases to check if a user can update or delete other user's tasks
def test_member_get_task_owned_by_other(client, db_session, test_bob_token):
    carol = db_session.query(User).filter(User.username == "carol").first()

    # Get the list of tasks owned by carol
    response = client.get(
        "/tasks/",
        params={"owner_id": carol.id},
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    carol_1st_task = response_content[0]

    # Get detail of the first task owned by carol
    response = client.get(
        f"/tasks/{carol_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 403
    response_data = response.json()
    assert response_data["detail"] == "Not authorized to view this task"


def test_member_update_task_owned_by_other(client, db_session, test_bob_token):
    carol = db_session.query(User).filter(User.username == "carol").first()

    # Get the list of tasks owned by carol
    response = client.get(
        "/tasks/",
        params={"owner_id": carol.id},
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    carol_1st_task = response_content[0]

    # Get detail of the first task owned by carol
    response = client.get(
        f"/tasks/{carol_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )
    response = client.put(
        f"/tasks/{carol_1st_task['id']}",
        json={
            "title": "Updated by Bob",
            "status": "in_progress",
        },
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 403
    response_data = response.json()
    assert response_data["detail"] == "Not authorized to view this task"


def test_member_delete_task_owned_by_other(client, db_session, test_bob_token):
    carol = db_session.query(User).filter(User.username == "carol").first()

    # Get the list of tasks owned by carol
    response = client.get(
        "/tasks/",
        params={"owner_id": carol.id},
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 200
    response_content = response.json()
    carol_1st_task = response_content[0]

    # Get detail of the first task owned by carol
    response = client.get(
        f"/tasks/{carol_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )
    response = client.delete(
        f"/tasks/{carol_1st_task['id']}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 403
    response_data = response.json()
    assert response_data["detail"] == "Not authorized to view this task"


# Check if member can delete another member
def test_member_delete_another_member(client, db_session, test_bob_token):
    carol = db_session.query(User).filter(User.username == "carol").first()

    # Bob deletes Carol
    response = client.delete(
        f"/users/{carol.id}",
        headers={"Authorization": f"Bearer {test_bob_token}"},
    )

    assert response.status_code == 403
    # Check if Carol is deleted from the database
    carol = db_session.query(User).filter(User.username == "carol").first()
    assert carol is not None


# Check if admin can delete a member
def test_admin_delete_member(client, db_session, test_admin_token):
    bob = db_session.query(User).filter(User.username == "bob").first()

    # Admin deletes Bob
    response = client.delete(
        f"/users/{bob.id}",
        headers={"Authorization": f"Bearer {test_admin_token}"},
    )

    assert response.status_code == 204

    # Check if Bob is deleted from the database
    deleted_bob = db_session.query(User).filter(User.id == bob.id).first()
    assert deleted_bob is None
