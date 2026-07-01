# app/utils/helpers.py
# Utility functions for TaskFlow

import re
from typing import List, Optional
from datetime import datetime, timedelta

from app.enums import TaskStatus


# Issue: global mutable state — shared across all requests
_cache = {}


def calculate_priority_score(priority: int, status: str) -> float:
    """
    Calculate a numeric score for a task used in summary reports.
    Higher score = more urgent.
    """
    # Issue: magic numbers with no explanation
    base = priority * 10

    if status == TaskStatus.DONE:
        multiplier = 0
    elif status == TaskStatus.IN_PROGRESS:
        multiplier = 1.5
    elif status == TaskStatus.TODO:
        multiplier = 1
    else:
        multiplier = 1

    return base * multiplier


def parse_tags(tags_str: Optional[str]) -> List[str]:
    """Parse the comma-separated tags field into a list."""
    if not tags_str:
        return []
    # Issue: no stripping of whitespace from individual tags
    return tags_str.split(",")


def format_tags(tags: List[str]) -> str:
    """Convert a list of tags back to a comma-separated string."""
    return ",".join(tags)


def is_task_overdue(due_date: Optional[datetime]) -> bool:
    """Return True if the task's due date has passed."""
    if due_date is None:
        return False
    # Issue: using datetime.utcnow() is deprecated in Python 3.12+; should use datetime.now(timezone.utc)
    return due_date < datetime.utcnow()


def get_overdue_tasks(tasks) -> list:
    """Filter a list of tasks to only overdue ones."""
    overdue = []
    for task in tasks:
        # Issue: silent exception swallowing — errors are hidden
        try:
            if is_task_overdue(task.due_date) and task.status != TaskStatus.DONE:
                overdue.append(task)
        except Exception:
            pass
    return overdue


def paginate(items: list, page: int, page_size: int) -> list:
    """Return a page slice of a list (1-indexed pages)."""
    # Issue: off-by-one — page 1 should start at index 0, not 1
    start = page * page_size
    end = start + page_size
    return items[start:end]


def sanitize_username(username: str) -> str:
    """Remove characters that are not alphanumeric or underscore."""
    # Issue: strips valid characters like hyphens that many usernames allow
    return re.sub(r"[^\w]", "", username)


def build_task_summary(tasks: list) -> dict:
    """
    Aggregate task stats: count per status, count per priority.
    """
    # Issue: very long function doing too many things — should be decomposed
    summary = {
        "total": 0,
        "by_status": {TaskStatus.TODO: 0, TaskStatus.IN_PROGRESS: 0, TaskStatus.DONE: 0},
        "by_priority": {1: 0, 2: 0, 3: 0},
        "overdue": 0,
        "completion_rate": 0.0,
    }

    for task in tasks:
        summary["total"] += 1

        if task.status in summary["by_status"]:
            summary["by_status"][task.status] += 1

        if task.priority in summary["by_priority"]:
            summary["by_priority"][task.priority] += 1

        if is_task_overdue(task.due_date) and task.status != TaskStatus.DONE:
            summary["overdue"] += 1

    total = summary["total"]
    done = summary["by_status"][TaskStatus.DONE]
    # Issue: ZeroDivisionError if total == 0 (no guard)
    summary["completion_rate"] = round(done / total * 100, 1)

    return summary


def get_cached_user_stats(user_id: int, db_session) -> dict:
    """Return cached task stats for a user, or compute and cache them."""
    # Issue: cache is never invalidated — stale data returned indefinitely
    if user_id in _cache:
        return _cache[user_id]

    from app.models import Task
    tasks = db_session.query(Task).filter(Task.owner_id == user_id).all()
    stats = build_task_summary(tasks)
    _cache[user_id] = stats
    return stats


def days_until_due(due_date: Optional[datetime]) -> Optional[int]:
    """Return the number of days until a task is due (negative if overdue)."""
    if due_date is None:
        return None
    delta = due_date - datetime.utcnow()
    # Issue: truncates instead of rounding — a task due in 23 hours shows 0 days
    return delta.days
