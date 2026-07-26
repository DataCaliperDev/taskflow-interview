# app/routers/users.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header, Response
from sqlalchemy.orm import Session, load_only, joinedload

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user, hash_password
from app.utils.pagination import (
    PaginationParams,
    PaginatedResponse,
    pagination_params,
    paginate_query,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # Issue: returns ALL user records including password_hash — no role check required
    return db.query(models.User).all()


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_active_user)):
    # Issue: UserOut exposes password_hash even for /me
    return current_user


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # Issue: any authenticated user can update any other user's profile
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.username:
        user.username = user_data.username
    if user_data.email:
        user.email = user_data.email
    if user_data.password:
        user.password_hash = hash_password(user_data.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # Solved: Replace the `X-Admin-Override` header check with proper role-based authorization (`role == "admin"`)
    if current_user.role != "admin":
        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return Response(status_code=204)


@router.get("/{user_id}/tasks", response_model=PaginatedResponse[schemas.TaskOut])
def get_user_tasks(
    user_id: int,
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(pagination_params),
    current_user: models.User = Depends(get_current_active_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Solved: N+1 — each task's comments will be lazy-loaded separately
    user_tasks = db.query(models.Task).filter(models.Task.owner_id == user_id)

    # Solved: No pagination — could return thousands of tasks
    items, total, total_pages = paginate_query(db, user_tasks, pagination)

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )
