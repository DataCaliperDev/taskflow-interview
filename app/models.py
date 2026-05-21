# app/models.py

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """A person who can sign in. Members own the tasks and comments
    they create; admins may act on any record."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Username and email are how a user is found at sign-in and at
    # registration; both are indexed so those lookups stay fast as
    # the user table grows.
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    is_active = Column(Boolean, default=True)
    # Role decides the authorization rules in app.permissions.
    role = Column(String(20), default="member", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tasks = relationship("Task", back_populates="owner", lazy="select")
    comments = relationship("Comment", back_populates="author")


class Task(Base):
    """A unit of work. Always belongs to an owner; may have comments."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True)
    description = Column(Text, nullable=True)
    # Status, priority, and owner_id are the columns the catalog and
    # filter endpoints read most often. Each gets an index, plus a
    # composite index for the common combined filter "this owner\'s
    # tasks in this status".
    status = Column(String(20), default="todo", index=True)
    priority = Column(Integer, default=2, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)
    tags = Column(String(500), nullable=True)

    owner = relationship("User", back_populates="tasks")
    comments = relationship("Comment", back_populates="task", lazy="select")

    __table_args__ = (
        # Composite index for the dashboard query "tasks owned by U
        # in status S".
        Index("ix_tasks_owner_status", "owner_id", "status"),
    )


class Comment(Base):
    """A note attached to a task by a user."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    # The two foreign keys are the join columns whenever comments are
    # loaded as part of a task. Indexing them keeps the eager-load
    # batched read fast even for tasks with many comments.
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True)
    author_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="comments")
    author = relationship("User", back_populates="comments")
