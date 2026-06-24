from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user
from app.utils.helpers import calculate_priority_score, parse_tags

router = APIRouter(prefix="/tasks", tags=["tasks"])


def can_manage_task(user: models.User, task: models.Task) -> bool:
    return user.role == "admin" or task.owner_id == user.id


def require_task_manager(user: models.User, task: models.Task) -> None:
    if not can_manage_task(user, task):
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/", response_model=List[schemas.TaskOut])
def list_tasks(
    status: Optional[str] = None,
    owner_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return all tasks. Optionally filter by status or owner."""
    query = db.query(models.Task)
    if status:
        query = query.filter(models.Task.status == status)
    if owner_id:
        query = query.filter(models.Task.owner_id == owner_id)
    return query.all()


@router.get("/search")
def search_tasks(
    q: str = Query(..., description="Search term"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Search tasks by title."""
    result = db.query(models.Task).filter(models.Task.title.ilike(f"%{q}%")).all()
    return [schemas.TaskOut.model_validate(task).model_dump(mode="json") for task in result]


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=schemas.TaskOut, status_code=200)
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
    require_task_manager(current_user, task)

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
    require_task_manager(current_user, task)

    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


@router.get("/summary/by-user", response_model=List[dict])
def task_summary_by_user(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return each user's task count and average priority score."""
    users = db.query(models.User).all()
    result = []

    for user in users:
        tasks = db.query(models.Task).filter(models.Task.owner_id == user.id).all()
        scores = [calculate_priority_score(t.priority, t.status) for t in tasks]
        avg_score = sum(scores) / len(scores) if scores else 0

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
