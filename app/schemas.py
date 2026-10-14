# app/schemas.py

from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.config import VALID_PRIORITIES, VALID_STATUSES


# ── Reusable field types ─────────────────────────────────────────────────────

Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]
# Not stripped: leading/trailing spaces are part of the password
Password = Annotated[str, Field(min_length=8)]
TaskTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def _check_status(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {value!r}")
    return value


def _check_priority(value: Optional[int]) -> Optional[int]:
    if value is not None and value not in VALID_PRIORITIES:
        raise ValueError(
            f"priority must be one of {VALID_PRIORITIES} (1=low, 2=medium, 3=high), got {value!r}"
        )
    return value


# ── Auth ────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: Username
    email: EmailStr
    password: Password


class UserUpdate(BaseModel):
    # Same rules as UserCreate so they cannot be bypassed via PUT
    username: Optional[Username] = None
    email: Optional[EmailStr] = None
    password: Optional[Password] = None


class UserOut(BaseModel):
    """Public representation of a user.

    Credentials (password_hash) are intentionally absent: every endpoint that
    returns a user goes through this schema, so they can never leak.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    role: str
    created_at: datetime


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


# ── Comment ───────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author_id: int
    created_at: datetime


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: TaskTitle
    description: Optional[str] = None
    status: str = "todo"
    priority: int = 2
    due_date: Optional[datetime] = None
    tags: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _check_status(value)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        return _check_priority(value)


class TaskUpdate(BaseModel):
    title: Optional[TaskTitle] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: Optional[str] = None

    @field_validator("title", "status", "priority")
    @classmethod
    def reject_explicit_null(cls, value):
        # Omitting a field leaves it unchanged; sending null would write NULL
        # into a required column, so reject it.
        if value is None:
            raise ValueError("may be omitted but cannot be null")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        return _check_status(value)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[int]) -> Optional[int]:
        return _check_priority(value)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    status: str
    priority: int
    owner_id: int
    created_at: datetime
    due_date: Optional[datetime]
    tags: Optional[str]
    comments: List[CommentOut] = []
