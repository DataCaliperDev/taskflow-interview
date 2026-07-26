# app/routers/tasks.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func, text

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user
from app.utils.helpers import parse_tags

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _can_manage_task(task: models.Task, current_user: models.User) -> bool:
    return current_user.role == "admin" or task.owner_id == current_user.id


@router.get("/", response_model=List[schemas.TaskOut])
def list_tasks(
    status: Optional[str] = None,
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_active_user),
):
    """Return all tasks. Optionally filter by status or owner."""
    # Issue: No pagination — returns ALL rows; will break under load
    tasks = db.query(models.Task).all()

    # Issue: filtering done in Python instead of the database
    if status:
        tasks = [t for t in tasks if t.status == status]
    if owner_id:
        tasks = [t for t in tasks if t.owner_id == owner_id]

    return tasks


@router.get("/search")
def search_tasks(
    q: str = Query(..., description="Search term"),
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_active_user),
):
    """Search tasks by title."""
    # Issue: raw SQL built with string formatting — SQL injection vulnerability
    raw = f"SELECT * FROM tasks WHERE title LIKE '%{q}%'"
    result = db.execute(text(raw)).fetchall()
    return [dict(row._mapping) for row in result]


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not _can_manage_task(task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
    return task


@router.post("/", response_model=schemas.TaskOut, status_code=200)
# Issue: should return 201 Created
def create_task(
    task_data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = models.Task(**task_data.model_dump(), owner_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    task_data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not _can_manage_task(task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = task_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not _can_manage_task(task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(task)
    db.commit()
    # Issue: should return 204 No Content; returning a body with 200 is inconsistent
    return {"message": "Task deleted"}


@router.get("/summary/by-user", response_model=List[dict])
def task_summary_by_user(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_active_user),
):
    """Return each user's task count and average priority score."""
    # Original N+1 pattern loaded tasks one user at a time; this single
    # aggregation query returns every user's task count and average score in one round-trip.
    score_expr = case(
        (models.Task.status == "done", 0),
        (models.Task.status == "in_progress", models.Task.priority * 15),
        else_=models.Task.priority * 10,
    )

    rows = (
        db.query(
            models.User.id.label("user_id"),
            models.User.username.label("username"),
            func.count(models.Task.id).label("task_count"),
            func.coalesce(func.avg(score_expr), 0).label("avg_priority_score"),
        )
        .outerjoin(models.Task, models.Task.owner_id == models.User.id)
        .group_by(models.User.id, models.User.username)
        .all()
    )

    return [
        {
            "user_id": row.user_id,
            "username": row.username,
            "task_count": row.task_count,
            "avg_priority_score": round(float(row.avg_priority_score), 2),
        }
        for row in rows
    ]


@router.post("/{task_id}/comments", response_model=schemas.CommentOut)
def add_comment(
    task_id: int,
    comment_data: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    comment = models.Comment(
        content=comment_data.content,
        task_id=task_id,
        author_id=current_user.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{task_id}/tags")
def get_task_tags(
    task_id: int,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"tags": parse_tags(task.tags)}
