# app/routers/tasks.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user
from app.utils.helpers import calculate_priority_score, parse_tags

router = APIRouter(prefix="/tasks", tags=["tasks"])


def require_admin_or_task_owner(current_user: models.User, task: models.Task) -> None:
    """Raise 403 if the current user is not an admin and does not own the task."""
    if current_user.role != "admin" and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/", response_model=List[schemas.TaskOut])
def list_tasks(
    status: Optional[str] = None,
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
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
    current_user: models.User = Depends(get_current_active_user),
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
    # Issue: no authorization check — any authenticated user can read any task
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

    require_admin_or_task_owner(current_user, task)
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

    require_admin_or_task_owner(current_user, task)
    db.delete(task)
    db.commit()
    # Issue: should return 204 No Content; returning a body with 200 is inconsistent
    return {"message": "Task deleted"}


@router.get("/summary/by-user", response_model=List[dict])
def task_summary_by_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return each user's task count and average priority score."""
    # Original problem (N+1):
    #   db.query(models.User).all() fetched all users in 1 query, then
    #   inside the loop db.query(models.Task).filter(owner_id == user.id).all()
    #   fired a separate SELECT for every user — 1 + N round-trips total.
    #
    # Fix — joinedload:
    #   Tells SQLAlchemy to eagerly load the tasks relationship using a single
    #   LEFT OUTER JOIN, so all users and their tasks are fetched in 1 query:
    #     SELECT users.*, tasks.*
    #     FROM users LEFT OUTER JOIN tasks ON tasks.owner_id = users.id
    #   Accessing user.tasks inside the loop hits no database — data is already
    #   hydrated from that single result set.
    #
    # Note — consider switchting to selectinload if the tasks table grows very large:
    #   joinedload uses a LEFT OUTER JOIN which multiplies result rows
    #   (1 user with 1 000 tasks = 1 000 rows for that user in the result set).
    #   selectinload instead runs a second query:
    #     SELECT * FROM tasks WHERE owner_id IN (1, 2, 3, ...)
    #   keeping the row count flat and avoiding the cartesian-product overhead.
    #   Switch by replacing joinedload with selectinload (same import path:
    #   from sqlalchemy.orm import selectinload).
    users = (
        db.query(models.User)
        .options(joinedload(models.User.tasks))
        .all()
    )
    result = []

    for user in users:
        tasks = user.tasks  # already loaded — no extra query fired here
        scores = [calculate_priority_score(t.priority, t.status) for t in tasks]
        if not scores:
            avg_score = 0.0
        else:
            avg_score = sum(scores) / len(scores)

        result.append({
            "user_id": user.id,
            "username": user.username,
            "task_count": len(tasks),
            "avg_priority_score": round(avg_score, 2),
        })

    return result


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
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"tags": parse_tags(task.tags)}
