# app/routers/tasks.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user, require_owner_or_admin
from app.utils.helpers import calculate_priority_score, parse_tags

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

    # UC-3: only the task's owner OR an admin may modify it.
    require_owner_or_admin(task.owner_id, current_user)

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

    # UC-3: only the task's owner OR an admin may delete it.
    require_owner_or_admin(task.owner_id, current_user)

    db.delete(task)
    db.commit()
    # Issue: should return 204 No Content; returning a body with 200 is inconsistent
    return {"message": "Task deleted"}


@router.get("/summary/by-user", response_model=List[dict])
def task_summary_by_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return each user's task count and average priority score.

    UC-5 — N+1 fix.

    Original problem:
        The previous implementation issued one SELECT to fetch all users and
        then *one additional SELECT per user* to load that user's tasks. For
        N users that is 1 + N round-trips to the database — a classic N+1
        that scales linearly with row count and dominates latency once the
        users table has any real size.

    Fix:
        Eager-load the `User.tasks` relationship with `joinedload`. SQLAlchemy
        emits a single SELECT containing a LEFT OUTER JOIN between `users`
        and `tasks`, hydrates each User with its `tasks` collection in one
        round-trip, and we can iterate in pure Python without any further
        I/O. Total queries: 1, regardless of N.

    Trade-off considered:
        A pure-SQL aggregation (GROUP BY user.id with COUNT and AVG over a
        CASE expression for priority * status) would be even more efficient
        at very large scales because it avoids transferring every task row.
        Rejected for now because it would duplicate the
        `calculate_priority_score` business rule as a SQL CASE — two
        implementations of the same formula is a maintenance trap. If the
        users-with-many-tasks workload ever becomes a bottleneck, the right
        move is to push `calculate_priority_score` into a hybrid SQL
        expression so both Python and SQL stay in sync, then switch this
        endpoint to GROUP BY.

    Response schema is unchanged.
    """
    users = (
        db.query(models.User)
        .options(joinedload(models.User.tasks))
        .all()
    )

    result = []
    for user in users:
        scores = [
            calculate_priority_score(t.priority, t.status) for t in user.tasks
        ]
        # Guard against empty task list — kept as in the original logic.
        avg_score = sum(scores) / len(scores) if scores else 0

        result.append({
            "user_id": user.id,
            "username": user.username,
            "task_count": len(user.tasks),
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
