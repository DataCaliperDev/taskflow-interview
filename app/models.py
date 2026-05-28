# app/models.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # Issue: no index on `email` despite being used as lookup key
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True)
    email = Column(String(100), unique=True)
    password_hash = Column(String(255))
    # Session invalidation knob:
    # increment this to invalidate all previously issued JWTs for the user.
    token_version = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="member")  # "admin" or "member"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tasks = relationship("Task", back_populates="owner", lazy="select")
    comments = relationship("Comment", back_populates="author")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200))
    description = Column(Text, nullable=True)
    status = Column(String(20), default="todo")   # todo | in_progress | done
    priority = Column(Integer, default=2)          # 1=low, 2=medium, 3=high
    owner_id = Column(Integer, ForeignKey("users.id"))
    # Issue: no index on `status` and `owner_id` which are heavily filtered on
    # Issue: no `updated_at` column for tracking modifications
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)
    tags = Column(String(500), nullable=True)   # Issue: comma-separated strings instead of a Tag table

    owner = relationship("User", back_populates="tasks")
    comments = relationship("Comment", back_populates="task", lazy="select")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="comments")
    author = relationship("User", back_populates="comments")
