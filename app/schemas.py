# app/schemas.py

from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from datetime import datetime

# UC-2: placeholder returned in place of the real password hash. The key stays
# in the response for one deprecation window because there is no request
# logging to tell us whether anything besides the React frontend consumes these
# endpoints; removing it blind would break such a client silently.
MASKED_PASSWORD_HASH = "***"


# ── Auth ────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    # Issue: no field-level validation — no min length, no email format check, no password strength


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    password_hash: str = Field(
        deprecated=True,
        description=(
            'Deprecated: always returns "***". Scheduled for removal one month '
            "after this release."
        ),
    )
    is_active: bool
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("password_hash")
    def _mask_password_hash(self, _value: str) -> str:
        """Always emit the placeholder, whatever was loaded from the database.

        Masking here rather than at each endpoint means the real hash cannot
        reach the wire through any of the five routes that return UserOut, and
        cannot be reintroduced by passing an ORM object in directly.
        """
        return MASKED_PASSWORD_HASH


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
    title: str
    description: Optional[str] = None
    status: Optional[str] = "todo"
    priority: Optional[int] = 2
    due_date: Optional[datetime] = None
    tags: Optional[str] = None
    # Issue: no validation that status is one of the valid values
    # Issue: no validation that priority is 1, 2, or 3


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: Optional[str] = None


class TaskSummaryRow(BaseModel):
    """One row of GET /tasks/summary/by-user.

    The endpoint previously declared List[dict], which documented nothing and
    validated nothing. The four keys and their types are unchanged — this only
    writes down the shape that was already being returned.
    """

    user_id: int
    username: str
    task_count: int
    avg_priority_score: float


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
