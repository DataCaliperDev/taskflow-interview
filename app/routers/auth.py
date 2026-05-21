"""Auth endpoints (register, login) and the dependency that resolves
the calling user from the bearer token.

Every UC-3 protected endpoint depends on ``get_current_active_user``;
that dependency is what makes the caller\'s role available to the
``require_*`` rules in ``app.permissions``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    # Out of scope for this PR: MD5 is cryptographically broken. The
    # migration to a strong hash is tracked separately; the algorithm
    # is preserved here so seeded passwords keep working.
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password


def create_access_token(
    data: schemas.JwtClaims, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode: dict[str, object] = dict(data)
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode["exp"] = expire
    # Signing secret comes from configuration -- never hardcoded (UC-4).
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        # The decoded value is loosely typed; only a real string
        # identifies a user.
        if not isinstance(username, str):
            # ``from None`` -- token validation failures must not leak
            # cryptographic details into the response chain.
            raise credentials_exception from None
    except JWTError:
        raise credentials_exception from None

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Resolve the calling user. Used by every UC-3 protected endpoint
    so the caller\'s role is available to the authorization rules."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=schemas.UserPublic, status_code=201)
def register(
    user_data: schemas.UserCreate, db: Session = Depends(get_db)
) -> models.User:
    # Reject duplicates explicitly so the caller gets a clear error
    # instead of a database constraint violation.
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(models.User).filter(models.User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = models.User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # Returned via UserPublic, which never includes the password hash.
    return new_user
