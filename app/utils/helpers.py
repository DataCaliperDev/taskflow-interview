import re
from typing import List, Optional, Dict, Any, Sequence
from datetime import datetime, timezone


STATUS_MULTIPLIERS: Dict[str, float] = {
    "done": 0.0,
    "in_progress": 1.5,
    "todo": 1.0,
}

PRIORITY_WEIGHT: int = 10


def calculate_priority_score(priority: int, status: str) -> float:
    base = priority * PRIORITY_WEIGHT
    multiplier = STATUS_MULTIPLIERS.get(status, 1.0)
    return base * multiplier


def parse_tags(tags_str: Optional[str]) -> List[str]:
    if not tags_str:
        return []
    return [tag.strip() for tag in tags_str.split(",") if tag.strip()]


def format_tags(tags: List[str]) -> str:
    return ",".join(tags)


def is_task_overdue(due_date: Optional[datetime]) -> bool:
    if due_date is None:
        return False
    return _as_aware(due_date) < datetime.now(timezone.utc)


def get_overdue_tasks(tasks: Sequence[Any]) -> List[Any]:
    return [
        task
        for task in tasks
        if is_task_overdue(task.due_date) and task.status != "done"
    ]


def paginate(items: List[Any], page: int, page_size: int) -> List[Any]:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


def sanitize_username(username: str) -> str:
    return re.sub(r"[^\w-]", "", username)


def _count_by_status(tasks: Sequence[Any]) -> Dict[str, int]:
    counts = {"todo": 0, "in_progress": 0, "done": 0}
    for task in tasks:
        if task.status in counts:
            counts[task.status] += 1
    return counts


def _count_by_priority(tasks: Sequence[Any]) -> Dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0}
    for task in tasks:
        if task.priority in counts:
            counts[task.priority] += 1
    return counts


def _completion_rate(total: int, done: int) -> float:
    if total == 0:
        return 0.0
    return round(done / total * 100, 1)


def build_task_summary(tasks: Sequence[Any]) -> Dict[str, Any]:
    by_status = _count_by_status(tasks)
    by_priority = _count_by_priority(tasks)
    total = len(tasks)
    overdue = len(get_overdue_tasks(tasks))

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "overdue": overdue,
        "completion_rate": _completion_rate(total, by_status["done"]),
    }


def days_until_due(due_date: Optional[datetime]) -> Optional[int]:
    if due_date is None:
        return None
    delta = _as_aware(due_date) - datetime.now(timezone.utc)
    return round(delta.total_seconds() / 86400)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
