# app/config.py

from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the project root so it is found regardless of the
# working directory (run.py, scripts/seed_data.py, pytest, ...).
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables and/or `.env`.

    Real environment variables take precedence over values in `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    APP_NAME: str = "TaskFlow"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database — may embed credentials in production, so it is configurable
    DATABASE_URL: str = "sqlite:///./taskflow.db"

    # Security — no default: the app must not start with a guessable key
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        problems = "\n".join(
            f"  - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        raise RuntimeError(
            "Invalid or missing configuration:\n"
            f"{problems}\n"
            "Set these as environment variables or in a .env file "
            "(see .env.example)."
        ) from None


settings = _load_settings()


# ── Domain constants (not environment-specific) ──────────────────────────────

# Pagination
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# Task priorities
PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3

VALID_PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]
VALID_STATUSES = ["todo", "in_progress", "done"]
