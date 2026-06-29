import logging
from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.database import get_db
from app.routers.auth import get_current_active_user

logger = logging.getLogger("taskflow.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _resolve_tags(names: List[str], db: Session) -> List[models.Tag]:
    tags: List[models.Tag] = []
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        tag = db.query(models.Tag).filter(models.Tag.name == name).first()
        if tag is None:
            tag = models.Tag(name=name)
            db.add(tag)
        tags.append(tag)
    return tags


def _ensure_can_modify(task: models.Task, user: models.User) -> None:
    if task.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/", response_model=schemas.Page[schemas.TaskOut])
def list_tasks(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    owner_id: Optional[int] = None,
    tag: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> schemas.Page:
    query = db.query(models.Task)

    if status_filter:
        query = query.filter(models.Task.status == status_filter)
    if owner_id:
        query = query.filter(models.Task.owner_id == owner_id)
    if tag:
        query = query.filter(models.Task.tags.any(models.Tag.name == tag))

    total = query.count()
    tasks = (
        query.options(selectinload(models.Task.tags), selectinload(models.Task.comments))
        .order_by(models.Task.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return schemas.Page(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if page_size else 0,
    )


@router.get("/search", response_model=List[schemas.TaskOut])
def search_tasks(
    q: str = Query(..., description="Search term"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> List[models.Task]:
    return (
        db.query(models.Task)
        .filter(models.Task.title.ilike(f"%{q}%"))
        .options(selectinload(models.Task.tags), selectinload(models.Task.comments))
        .all()
    )


@router.get("/summary/by-user", response_model=List[dict])
def task_summary_by_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> List[dict]:
    status_multiplier = case(
        (models.Task.status == "done", 0.0),
        (models.Task.status == "in_progress", 1.5),
        else_=1.0,
    )

    rows = (
        db.query(
            models.User.id,
            models.User.username,
            func.count(models.Task.id),
            func.coalesce(
                func.avg(models.Task.priority * 10 * status_multiplier),
                0.0,
            ),
        )
        .outerjoin(models.Task, models.Task.owner_id == models.User.id)
        .group_by(models.User.id, models.User.username)
        .all()
    )

    return [
        {
            "user_id": user_id,
            "username": username,
            "task_count": task_count,
            "avg_priority_score": round(float(avg_score), 2),
        }
        for user_id, username, task_count, avg_score in rows
    ]


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Task:
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Task:
    payload = task_data.model_dump(exclude={"tags"})
    task = models.Task(**payload, owner_id=current_user.id)
    task.tags = _resolve_tags(task_data.tags, db)
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info("Task created: id=%s owner=%s", task.id, current_user.username)
    return task


@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    task_data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Task:
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _ensure_can_modify(task, current_user)

    update_data = task_data.model_dump(exclude_unset=True)
    if "tags" in update_data:
        task.tags = _resolve_tags(update_data.pop("tags") or [], db)
    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> None:
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _ensure_can_modify(task, current_user)

    db.delete(task)
    db.commit()
    logger.info("Task deleted: id=%s by=%s", task_id, current_user.username)


@router.post(
    "/{task_id}/comments",
    response_model=schemas.CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    task_id: int,
    comment_data: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Comment:
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
) -> dict:
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"tags": [tag.name for tag in task.tags]}
