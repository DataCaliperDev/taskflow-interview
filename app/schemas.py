# app/schemas.py

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime


# UC-9: shared type aliases keep the allowed values in one place so the
# constraint is identical on every endpoint that consumes a task status or
# priority. Updating the allowed set is a one-line change here.
TaskStatus = Literal["todo", "in_progress", "done"]
TaskPriority = int  # constrained at field level via Field(ge=1, le=3)


# ── Auth ────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    # UC-9: enforce minimum lengths and a real email format at the schema
    # boundary so bad inputs are rejected before they reach the database or
    # auth code paths.
    username: str = Field(min_length=3, description="At least 3 characters")
    email: EmailStr
    password: str = Field(min_length=8, description="At least 8 characters")


class UserUpdate(BaseModel):
    # UC-9: same constraints as UserCreate, but every field is optional so
    # callers can patch a subset. Omitting a field is fine; providing an
    # invalid value is not — otherwise PUT /users/{id} becomes a bypass for
    # the create-time rules.
    username: Optional[str] = Field(default=None, min_length=3)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)


class UserOut(BaseModel):
    # password_hash is intentionally NOT exposed here (UC-2). Every
    # user-facing endpoint serialises through UserOut, so removing the
    # field at the schema level guarantees it cannot leak from any route.
    id: int
    username: str
    email: str
    is_active: bool
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


# ── Comment ───────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    content: str
    author_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    # UC-9: title must be non-empty; status and priority are constrained at
    # the type level so any other value triggers a 422 with a clear message
    # listing the allowed values (status) or the permitted range (priority).
    title: str = Field(min_length=1, description="Must not be empty")
    description: Optional[str] = None
    status: TaskStatus = "todo"
    priority: int = Field(default=2, ge=1, le=3, description="1 (low) – 3 (high)")
    due_date: Optional[datetime] = None
    tags: Optional[str] = None


class TaskUpdate(BaseModel):
    # UC-9: partial updates — every field is optional, but supplied values
    # still go through the same constraints as TaskCreate.
    title: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    due_date: Optional[datetime] = None
    tags: Optional[str] = None


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

    model_config = ConfigDict(from_attributes=True)
