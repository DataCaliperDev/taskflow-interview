"""User endpoints. Domain rules tagged inline:

    UC-3   ownership and admin rules on profile update / delete
    UC-6   paginated list of a user\'s tasks
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.common.lookups import fetch_or_404
from app.database import get_db
from app.pagination import PageParams, paginate
from app.permissions import require_admin, require_self_or_admin
from app.routers.auth import get_current_active_user, hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[schemas.UserPublic])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.User]:
    return db.query(models.User).all()


@router.get("/me", response_model=schemas.UserPublic)
def get_me(
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    return current_user


@router.get("/{user_id}", response_model=schemas.UserPublic)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    user = fetch_or_404(db, models.User, user_id, "User")
    return user


@router.put("/{user_id}", response_model=schemas.UserPublic)
def update_user(
    user_id: int,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    """Update a user profile. UC-3: a user may edit their own profile;
    an admin may edit any profile."""
    # Authorization rule: self-or-admin.
    require_self_or_admin(current_user, user_id)

    user = fetch_or_404(db, models.User, user_id, "User")

    # Only write fields the caller actually sent. The password is
    # hashed before it touches the row so plaintext never reaches the
    # database.
    payload = user_data.model_dump(exclude_unset=True)
    plaintext_password = payload.pop("password", None)
    for field, value in payload.items():
        setattr(user, field, value)
    if plaintext_password is not None:
        user.password_hash = hash_password(plaintext_password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204, response_model=None)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> None:
    """Delete a user. UC-3: admins only.

    The legacy ``X-Admin-Override: admin-secret-2024`` header is gone;
    admin status is decided exclusively by ``role == "admin"``.
    """
    # Authorization rule: admin-only.
    require_admin(current_user)

    user = fetch_or_404(db, models.User, user_id, "User")

    db.delete(user)
    db.commit()
    return None


# A user\'s tasks, paged. UC-6.
@router.get("/{user_id}/tasks", response_model=schemas.Page[schemas.TaskOut])
def get_user_tasks(
    user_id: int,
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> schemas.PageDict:
    """List one page of tasks owned by ``user_id``."""
    fetch_or_404(db, models.User, user_id, "User")

    # Eager-load comments so rendering a page of tasks does not turn
    # into one comment read per task -- the cost stays constant
    # regardless of how many tasks the user owns on this page.
    query = (
        db.query(models.Task)
        .options(selectinload(models.Task.comments))
        .filter(models.Task.owner_id == user_id)
        .order_by(models.Task.id)
    )
    return paginate(query, page_params)
