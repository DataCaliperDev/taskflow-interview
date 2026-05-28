"""Wire shapes (request bodies and response payloads).

Two shapes encode domain rules that other layers depend on:

    UserPublic       -- the safe view of a user: identity, role,
                        activity, timestamps. Never includes the
                        password hash, even for the user themselves.
    TaskSummaryRow   -- one row of the per-user task summary
                        (UC-5). Stable schema so the aggregation
                        rewrite cannot drift the response.

List endpoints wrap their items in ``app.pagination.Page[T]`` (UC-6);
the item types live here.
"""

from datetime import datetime
from typing import Generic, List, Optional, TypedDict, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


# Auth
class JwtClaims(TypedDict, total=False):
    """Claims encoded in our access tokens.

    ``sub`` is the username of the bearer; ``exp`` is added by the
    token issuer.
    """

    sub: str
    exp: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# User
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserPublic(BaseModel):
    """The safe view of a user. Never carries the password hash."""

    id: int
    username: str
    email: str
    is_active: bool
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# Backwards-compat alias for code paths that import UserOut.
UserOut = UserPublic


class UserSummary(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


# Comment
class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    content: str
    author_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Task
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "todo"
    priority: Optional[int] = 2
    due_date: Optional[datetime] = None
    tags: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
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

    class Config:
        from_attributes = True




# Slim row returned by GET /tasks/search. Subset of TaskOut
# fields -- search results don\'t need to materialise comments.
class TaskSearchRow(BaseModel):
    id: int
    title: str
    status: str
    priority: int
    owner_id: int

    class Config:
        from_attributes = True




# Pagination wire shapes (UC-6). Page[T] is the response
# envelope every list endpoint returns; PageDict is the dict
# shape ``paginate()`` produces, which Pydantic coerces into
# Page[T] when the endpoint declares ``response_model=Page[T]``.
class PageDict(TypedDict):
    """The shape ``paginate()`` returns."""

    items: list[object]
    total: int
    page: int
    page_size: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    """Envelope a list endpoint returns. ``items`` is one page;
    the rest is the metadata a client uses to render navigation."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# Tag list returned by GET /tasks/{id}/tags.
class TaskTags(BaseModel):
    tags: List[str]


# One row of the per-user task summary (UC-5). Pulling this out as a
# named shape stops the aggregation rewrite from silently changing
# the response.
class TaskSummaryRow(BaseModel):
    user_id: int
    username: str
    task_count: int
    avg_priority_score: float
