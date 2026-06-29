# app/schemas.py

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime

from app.config import VALID_STATUSES, VALID_PRIORITIES


def _ensure_valid_status(v):
    if v not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")
    return v


def _ensure_valid_priority(v):
    if v not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {VALID_PRIORITIES}")
    return v


# ── Auth ────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    # UC-9: enforce a valid email, a username of at least 3 chars, and a
    # password of at least 8 chars. Invalid input surfaces as HTTP 422.
    username: str = Field(min_length=3)
    email: EmailStr
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    password_hash: str   # Issue: password hash is exposed in the response schema
    is_active: bool
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserSummary(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


# ── Comment ───────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    content: str
    author_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    # UC-9: title must be non-empty; status/priority must be in the valid sets.
    title: str = Field(min_length=1)
    description: Optional[str] = None
    status: Optional[str] = "todo"
    priority: Optional[int] = 2
    due_date: Optional[datetime] = None
    tags: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v):
        return _ensure_valid_status(v)

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v):
        return _ensure_valid_priority(v)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v):
        # All fields are optional on update — leave an omitted value untouched.
        if v is None:
            return v
        return _ensure_valid_status(v)

    @field_validator("priority")
    @classmethod
    def priority_must_be_valid(cls, v):
        if v is None:
            return v
        return _ensure_valid_priority(v)


class TaskOut(BaseModel):
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

    class Config:
        from_attributes = True
