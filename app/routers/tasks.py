"""Task endpoints. Domain rules tagged inline:

    UC-3   ownership and admin rules on update/delete
    UC-5   per-user task summary (counts + average score)
    UC-6   paginated catalog endpoints
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.common.lookups import fetch_or_404
from app.database import get_db
from app.pagination import PageParams, paginate
from app.permissions import require_owner_or_admin
from app.routers.auth import get_current_active_user
from app.utils.helpers import parse_tags

router = APIRouter(prefix="/tasks", tags=["tasks"])


# Task catalog: returns one page of tasks, optionally filtered by
# status or owner. Filters are applied in the database, not in the
# application, so they compose with paging cleanly.
@router.get("/", response_model=schemas.Page[schemas.TaskOut])
def list_tasks(
    status: str | None = None,
    owner_id: int | None = None,
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> schemas.PageDict:
    """List tasks (paged). UC-6."""
    # Each task carries its comments. Without eager loading, rendering
    # one page would issue a separate read for every task\'s comments
    # (1 + N statements). The eager-load pulls them all in a single
    # batched read so the cost stays constant across page sizes.
    query = db.query(models.Task).options(selectinload(models.Task.comments))
    if status:
        query = query.filter(models.Task.status == status)
    if owner_id:
        query = query.filter(models.Task.owner_id == owner_id)
    return paginate(query.order_by(models.Task.id), page_params)


@router.get("/search", response_model=list[schemas.TaskSearchRow])
def search_tasks(
    q: str = Query(..., description="Search term"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.Task]:
    """Find tasks whose title contains the search term."""
    return (
        db.query(models.Task)
        .filter(models.Task.title.ilike(f"%{q}%"))
        .all()
    )


# Per-user task summary -- UC-5.
#
# The original implementation walked every user and read their tasks
# in a separate query (1 + N reads). For a workspace with many users
# this turns one logical operation into a flood of database round
# trips. The rewrite expresses the same answer as a single grouped
# query: for every user, count their tasks and average a derived
# urgency score. Users with no tasks still appear, with zero counts.
@router.get("/summary/by-user", response_model=list[schemas.TaskSummaryRow])
def task_summary_by_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[schemas.TaskSummaryRow]:
    """Return one row per user with task count and average urgency.

    Urgency score (matches utils.helpers.calculate_priority_score):
        done         -> 0
        in_progress  -> priority * 15
        anything else -> priority * 10
    """
    score_expr = case(
        (models.Task.status == "done", 0.0),
        (models.Task.status == "in_progress", models.Task.priority * 15.0),
        else_=models.Task.priority * 10.0,
    )
    rows = (
        db.query(
            models.User.id.label("user_id"),
            models.User.username.label("username"),
            func.count(models.Task.id).label("task_count"),
            func.coalesce(func.avg(score_expr), 0.0).label("avg_priority_score"),
        )
        # Outer join keeps users who have no tasks in the result --
        # an inner join would silently drop them and the response
        # would no longer cover the whole workspace.
        .outerjoin(models.Task, models.Task.owner_id == models.User.id)
        .group_by(models.User.id, models.User.username)
        .order_by(models.User.id)
        .all()
    )
    return [
        schemas.TaskSummaryRow(
            user_id=r.user_id,
            username=r.username,
            task_count=int(r.task_count),
            avg_priority_score=round(float(r.avg_priority_score), 2),
        )
        for r in rows
    ]


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Task:
    task = fetch_or_404(db, models.Task, task_id, "Task")
    return task


@router.post("/", response_model=schemas.TaskOut, status_code=201)
def create_task(
    task_data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Task:
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
) -> models.Task:
    """Update a task. UC-3: only the task\'s owner or an admin may do this."""
    task = fetch_or_404(db, models.Task, task_id, "Task")

    # Authorization rule: owner-or-admin.
    require_owner_or_admin(current_user, task.owner_id)

    # Only write fields the caller actually sent.
    for key, value in task_data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204, response_model=None)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> None:
    """Delete a task. UC-3: only the task\'s owner or an admin may do this."""
    task = fetch_or_404(db, models.Task, task_id, "Task")

    # Authorization rule: owner-or-admin.
    require_owner_or_admin(current_user, task.owner_id)

    db.delete(task)
    db.commit()
    return None


@router.post(
    "/{task_id}/comments", response_model=schemas.CommentOut, status_code=201
)
def add_comment(
    task_id: int,
    comment_data: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Comment:
    fetch_or_404(db, models.Task, task_id, "Task")

    comment = models.Comment(
        content=comment_data.content,
        task_id=task_id,
        author_id=current_user.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{task_id}/comments", response_model=list[schemas.CommentOut])
def list_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.Comment]:
    task = fetch_or_404(db, models.Task, task_id, "Task")
    return list(task.comments)


@router.get("/{task_id}/tags", response_model=schemas.TaskTags)
def get_task_tags(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> schemas.TaskTags:
    task = fetch_or_404(db, models.Task, task_id, "Task")
    return schemas.TaskTags(tags=parse_tags(task.tags))
