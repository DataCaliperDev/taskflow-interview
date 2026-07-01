# app/enums.py

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
