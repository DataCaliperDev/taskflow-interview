# app/database.py

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_user_token_version_column()


def _ensure_user_token_version_column():
    """Best-effort lightweight migration for existing SQLite DB files.

    Older local DBs (e.g. taskflow.db) may not have `users.token_version`.
    That causes login/auth queries to crash after introducing session
    invalidation logic. For SQLite we can safely add the column in-place.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        table_info = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        existing_columns = {row[1] for row in table_info}
        if "token_version" in existing_columns:
            return
        conn.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
            )
        )
