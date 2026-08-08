# app/routers/tasks.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func, text

from app import models, schemas
from app.database import get_db
from app.permissions import require_owner_or_admin
from app.routers.auth import get_current_active_user
from app.utils.helpers import parse_tags

router = APIRouter(prefix="/tasks", tags=["tasks"])


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
    require_owner_or_admin(current_user, task.owner_id, "task")

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
    require_owner_or_admin(current_user, task.owner_id, "task")

    db.delete(task)
    db.commit()
    # Issue: should return 204 No Content; returning a body with 200 is inconsistent
    return {"message": "Task deleted"}


@router.get("/summary/by-user", response_model=List[schemas.TaskSummaryRow])
def task_summary_by_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return each user's task count and average priority score.

    This used to load every user and then issue one SELECT per user to fetch
    their tasks: 1 + N round trips that grew without bound (measured at 51
    statements for 50 users). It is now a single LEFT JOIN aggregation, so the
    cost is one statement however many users exist.

    The CASE below mirrors utils.helpers.calculate_priority_score. Restating the
    formula in SQL is the price of aggregating in the database rather than
    shipping every task row to the application; the parity test in
    tests/test_summary.py fails if the two definitions ever drift apart.
    """
    # LEFT JOIN, not JOIN: users with no tasks belong in the report with zeroes,
    # as they were under the old loop.
    score = case(
        (models.Task.status == "done", 0.0),
        (models.Task.status == "in_progress", models.Task.priority * 15.0),
        else_=models.Task.priority * 10.0,
    )

    rows = (
        db.query(
            models.User.id,
            models.User.username,
            # COUNT(tasks.id) rather than COUNT(*): the outer join pads users
            # who own nothing with a NULL row, which COUNT(*) would score as 1.
            func.count(models.Task.id),
            # AVG over no rows is NULL, so restore the zero the loop produced.
            func.coalesce(func.avg(score), 0.0),
        )
        .outerjoin(models.Task, models.Task.owner_id == models.User.id)
        .group_by(models.User.id, models.User.username)
        # The old version inherited insertion order by accident; make it a rule.
        .order_by(models.User.id)
        .all()
    )

    # Rounding stays in Python: round() is banker's rounding and SQL ROUND() is
    # not, so moving it into the query would shift values on .005 boundaries.
    return [
        {
            "user_id": user_id,
            "username": username,
            "task_count": task_count,
            "avg_priority_score": round(avg_score, 2),
        }
        for user_id, username, task_count, avg_score in rows
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
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"tags": parse_tags(task.tags)}
