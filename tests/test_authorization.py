# tests/test_authorization.py

"""
UC-3: ownership and role checks on task and user mutations.

Kept in one file so the whole authorization matrix reads together — the bug was
that four handlers each decided for themselves, and three of them decided wrong.
"""

import pytest

from app import models

# owner/self may act, a third party may not, an admin may act on anything.
ACTORS = [("owner", 200), ("other", 403), ("admin", 200)]


def _auth_for(actor, owner_auth, make_user):
    if actor == "owner":
        return owner_auth
    if actor == "other":
        return make_user("other")[1]
    return make_user("admin", role="admin")[1]


def _create_task(client, auth, title="original"):
    return client.post(
        "/tasks/",
        json={"title": title, "priority": 2, "status": "todo"},
        headers=auth,
    ).json()


# ── Tasks ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("actor, expected", ACTORS)
def test_task_update_authorization(client, make_user, actor, expected):
    _, owner_auth = make_user("owner")
    task = _create_task(client, owner_auth)

    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "changed"},
        headers=_auth_for(actor, owner_auth, make_user),
    )
    assert response.status_code == expected

    # A 403 has to mean nothing changed. A handler that writes first and refuses
    # afterwards would satisfy a status-code-only assertion.
    after = client.get(f"/tasks/{task['id']}", headers=owner_auth).json()
    assert after["title"] == ("original" if expected == 403 else "changed")


@pytest.mark.parametrize("actor, expected", ACTORS)
def test_task_delete_authorization(client, make_user, actor, expected):
    _, owner_auth = make_user("owner")
    task = _create_task(client, owner_auth)

    response = client.delete(
        f"/tasks/{task['id']}",
        headers=_auth_for(actor, owner_auth, make_user),
    )
    assert response.status_code == expected

    lookup = client.get(f"/tasks/{task['id']}", headers=owner_auth)
    assert lookup.status_code == (200 if expected == 403 else 404)


# ── Users ────────────────────────────────────────────────────────────────────

# "owner" of a user record is that user, so the labels shift but the rule does not.
USER_ACTORS = [("self", 200), ("other", 403), ("admin", 200)]


@pytest.mark.parametrize("actor, expected", USER_ACTORS)
def test_user_update_authorization(client, db_session, make_user, actor, expected):
    target, target_auth = make_user("target")
    new_name = "renamed"

    response = client.put(
        f"/users/{target['id']}",
        json={"username": new_name},
        headers=_auth_for(actor.replace("self", "owner"), target_auth, make_user),
    )
    assert response.status_code == expected

    # Read back from the database rather than the API: a successful rename
    # invalidates the target's own token, whose subject is the old username.
    db_session.expire_all()
    stored = db_session.query(models.User).filter(
        models.User.id == target["id"]
    ).first()
    assert stored.username == (target["username"] if expected == 403 else new_name)


@pytest.mark.parametrize("actor, expected", USER_ACTORS)
def test_user_delete_authorization(client, db_session, make_user, actor, expected):
    target, target_auth = make_user("target")

    response = client.delete(
        f"/users/{target['id']}",
        headers=_auth_for(actor.replace("self", "owner"), target_auth, make_user),
    )
    assert response.status_code == expected

    db_session.expire_all()
    survived = db_session.query(models.User).filter(
        models.User.id == target["id"]
    ).first() is not None
    assert survived == (expected == 403)


# ── Regressions ──────────────────────────────────────────────────────────────


def test_admin_override_header_no_longer_grants_access(client, db_session, make_user):
    """The magic header must not be a way back in.

    Proving the parameter was deleted is not enough — FastAPI would simply
    ignore an unknown header, so this asserts the request is refused and the
    target survives.
    """
    target, _ = make_user("target")
    _, attacker_auth = make_user("attacker")

    response = client.delete(
        f"/users/{target['id']}",
        headers={**attacker_auth, "X-Admin-Override": "admin-secret-2024"},
    )
    assert response.status_code == 403

    db_session.expire_all()
    assert db_session.query(models.User).filter(
        models.User.id == target["id"]
    ).first() is not None


def test_missing_resource_is_404_before_403(client, make_user):
    """Ordering is deliberate: the owner is unknown until the row is loaded.

    The trade-off is that 403 confirms an id exists, which this documents.
    """
    _, auth = make_user("nobody")

    assert client.put(
        "/tasks/999999", json={"title": "x"}, headers=auth
    ).status_code == 404
    assert client.delete("/users/999999", headers=auth).status_code == 404
