# app/routers/users.py

import math
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user, hash_password

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
    x_admin_override: str = Header(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # Issue: admin check via a custom header value instead of role-based access control
    # Any caller who knows the magic string can delete any user
    if x_admin_override != "admin-secret-2024":
        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.get("/{user_id}/tasks", response_model=schemas.TaskPage)
def get_user_tasks(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = (
        db.query(models.Task)
        .options(selectinload(models.Task.comments))
        .filter(models.Task.owner_id == user_id)
    )
    total = query.order_by(None).count()
    items = (
        query.order_by(models.Task.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0

    return schemas.TaskPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
