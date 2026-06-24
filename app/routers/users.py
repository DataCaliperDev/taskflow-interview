from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_active_user, hash_password

router = APIRouter(prefix="/users", tags=["users"])


def is_admin(user: models.User) -> bool:
    return user.role == "admin"


def require_self_or_admin(current_user: models.User, user_id: int) -> None:
    if current_user.id != user_id and not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return db.query(models.User).all()


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_active_user)):
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
    require_self_or_admin(current_user, user_id)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.username is not None:
        user.username = user_data.username
    if user_data.email is not None:
        user.email = str(user_data.email)
    if user_data.password is not None:
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
    require_self_or_admin(current_user, user_id)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.get("/{user_id}/tasks", response_model=List[schemas.TaskOut])
def get_user_tasks(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.tasks
