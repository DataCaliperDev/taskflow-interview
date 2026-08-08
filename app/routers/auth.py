# app/routers/auth.py

from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# UC-1: was hashlib.md5(). MD5 is fast enough to brute-force on a GPU and was
# used unsalted here, so equal passwords produced equal digests — rainbow-table
# reversible. bcrypt gives a per-hash salt and a tunable cost factor.
#
# hex_md5 stays registered but deprecated so legacy digests still verify and get
# upgraded on login. Drop it once no rows remain on the old scheme.
pwd_context = CryptContext(
    schemes=["bcrypt", "hex_md5"],
    deprecated=["hex_md5"],
)


def hash_password(password: str) -> str:
    """Hash with bcrypt. The salt is generated per call and embedded in the
    result, so one password never hashes to the same string twice.

    bcrypt silently truncates past 72 bytes; enforcing a maximum length is input
    validation and belongs to the schema layer.
    """
    return pwd_context.hash(password)


def verify_and_upgrade_password(
    plain_password: str, hashed_password: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """Verify a password, returning ``(is_valid, upgraded_hash)``.

    ``upgraded_hash`` is a fresh bcrypt hash when the stored one used a
    deprecated scheme, ``None`` when it is already current.

    MD5 is one-way, so existing hashes cannot be migrated in bulk — a successful
    login is the only moment the plaintext is available, which is why the
    re-hash happens there. No format branching is needed: bcrypt hashes are
    self-describing (``$2b$…``) and passlib identifies the scheme from the
    stored value, so no extra column is required to track it.
    """
    try:
        return pwd_context.verify_and_update(plain_password, hashed_password)
    except (UnknownHashError, ValueError, TypeError):
        # Unparseable hash (empty, corrupt, foreign format). Without this guard
        # passlib's exception escapes the handler and a bad credential returns
        # 500 instead of 401.
        return False, None


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Boolean-only check, for callers that cannot persist an upgraded hash."""
    is_valid, _ = verify_and_upgrade_password(plain_password, hashed_password)
    return is_valid


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    # Issue: algorithm is HS256 with a weak hardcoded secret — no RS256 or key rotation
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user=Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Issue: No rate limiting on the login endpoint — vulnerable to brute force
@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()

    is_valid, upgraded_hash = verify_and_upgrade_password(
        form_data.password, user.password_hash if user else None
    )

    if not user or not is_valid:
        # Issue: identical error for "user not found" vs "wrong password" is correct,
        # but the response leaks timing info — no constant-time comparison
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # UC-1 lazy migration: overwrite the legacy digest in place, which destroys
    # it rather than archiving it. Costs one write per account (first sign-in
    # after deploy) and spares everyone a forced password reset.
    if upgraded_hash:
        user.password_hash = upgraded_hash
        db.commit()

    token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=schemas.UserOut, status_code=200)
# Issue: should return 201 Created, not 200
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(
        models.User.email == user_data.email
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Issue: no check for duplicate username
    new_user = models.User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
