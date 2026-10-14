# tests/test_indexes.py

"""
UC-7: indexes exist and are used by the filtered queries.
"""

import pytest
from sqlalchemy import inspect, text

from tests.conftest import engine


def _indexed_columns(table):
    return {
        tuple(ix["column_names"]): bool(ix.get("unique"))
        for ix in inspect(engine).get_indexes(table)
    }


def test_task_filter_columns_are_indexed():
    indexes = _indexed_columns("tasks")

    assert ("status",) in indexes
    assert ("owner_id",) in indexes


def test_user_email_has_unique_index():
    indexes = _indexed_columns("users")

    assert indexes.get(("email",)) is True


@pytest.mark.parametrize("where, index_name", [
    ("status = 'todo'", "ix_tasks_status"),
    ("owner_id = 1", "ix_tasks_owner_id"),
])
def test_task_filters_use_index(where, index_name):
    with engine.connect() as conn:
        plan = conn.execute(text(f"EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE {where}")).fetchall()

    assert any(index_name in row[-1] for row in plan), plan


def test_email_lookup_uses_index():
    with engine.connect() as conn:
        plan = conn.execute(text(
            "EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = 'a@example.com'"
        )).fetchall()

    assert any("ix_users_email" in row[-1] for row in plan), plan
