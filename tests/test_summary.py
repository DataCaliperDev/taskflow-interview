# tests/test_summary.py

"""
UC-5: GET /tasks/summary/by-user must cost one query, not one per user.

The endpoint function is called directly rather than over HTTP so the
authentication lookup does not land in the statement count.
"""

import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import event

from app import models
from app.routers.tasks import task_summary_by_user
from app.utils.helpers import calculate_priority_score


@contextmanager
def count_queries(session):
    """Record every statement the session's engine executes inside the block."""
    engine = session.get_bind()
    seen = []

    def _record(conn, cursor, statement, *_):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def _add_user(db, tasks):
    """Create a user owning `tasks`, given as (priority, status) pairs."""
    name = f"summary-{uuid.uuid4().hex[:8]}"
    user = models.User(username=name, email=f"{name}@example.com", password_hash="x")
    db.add(user)
    db.commit()

    for priority, status in tasks:
        db.add(models.Task(
            title="t", owner_id=user.id, priority=priority, status=status,
        ))
    db.commit()
    return user


@pytest.mark.parametrize("n_users", [1, 5, 20])
def test_summary_cost_does_not_grow_with_the_number_of_users(db_session, n_users):
    """The point of the fix: constant cost, not merely a smaller one.

    A single measurement would only show the endpoint currently issues one
    query. Repeating it across user counts is what demonstrates the 1 + N
    relationship is gone — before this change these ran 2, 6 and 21 statements.
    """
    for _ in range(n_users):
        _add_user(db_session, [(2, "todo"), (3, "in_progress")])

    with count_queries(db_session) as statements:
        task_summary_by_user(db=db_session, current_user=None)

    assert len(statements) == 1, statements


def test_summary_matches_the_python_scoring_helper(db_session):
    """Parity guard for the formula that now exists in both Python and SQL.

    Recomputes the expected values with calculate_priority_score itself, so
    editing one definition without the other turns this red.
    """
    _add_user(db_session, [(3, "in_progress"), (2, "todo"), (1, "done")])
    _add_user(db_session, [(3, "done"), (2, "done")])
    _add_user(db_session, [])
    _add_user(db_session, [(2, "archived")])   # unknown status → the ELSE branch

    rows = {r["user_id"]: r for r in task_summary_by_user(
        db=db_session, current_user=None,
    )}

    for user in db_session.query(models.User).all():
        tasks = db_session.query(models.Task).filter(
            models.Task.owner_id == user.id
        ).all()
        scores = [calculate_priority_score(t.priority, t.status) for t in tasks]
        expected = round(sum(scores) / len(scores), 2) if scores else 0

        assert rows[user.id]["task_count"] == len(tasks), user.username
        assert rows[user.id]["avg_priority_score"] == expected, user.username


def test_users_without_tasks_stay_in_the_report(db_session):
    """Catches both an inner join and COUNT(*).

    An inner join would drop the user entirely; COUNT(*) would report 1 for the
    NULL-padded row the outer join produces.
    """
    user = _add_user(db_session, [])

    row = next(
        r for r in task_summary_by_user(db=db_session, current_user=None)
        if r["user_id"] == user.id
    )
    assert row["task_count"] == 0
    assert row["avg_priority_score"] == 0


def test_a_zero_average_is_distinguishable_from_having_no_tasks(db_session):
    """Completed work scores zero, which must not read as an empty backlog."""
    user = _add_user(db_session, [(3, "done"), (2, "done")])

    row = next(
        r for r in task_summary_by_user(db=db_session, current_user=None)
        if r["user_id"] == user.id
    )
    assert row["task_count"] == 2
    assert row["avg_priority_score"] == 0


def test_summary_is_ordered_by_user_id(db_session):
    """The old loop inherited insertion order by accident; this makes it a rule."""
    for _ in range(4):
        _add_user(db_session, [(1, "todo")])

    ids = [r["user_id"] for r in task_summary_by_user(
        db=db_session, current_user=None,
    )]
    assert ids == sorted(ids)


def test_response_shape_is_unchanged(client, make_user):
    """The endpoint now declares a schema; the wire format must not move."""
    _, auth = make_user("summary")

    response = client.get("/tasks/summary/by-user", headers=auth)
    assert response.status_code == 200

    row = response.json()[0]
    assert set(row) == {"user_id", "username", "task_count", "avg_priority_score"}
    assert isinstance(row["user_id"], int)
    assert isinstance(row["username"], str)
    assert isinstance(row["task_count"], int)
    assert isinstance(row["avg_priority_score"], float)
