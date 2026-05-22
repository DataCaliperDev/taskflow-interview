# app/config.py

import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Application configuration
APP_NAME = os.getenv("APP_NAME", "TaskFlow")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DEBUG = _env_bool("DEBUG", True)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./taskflow.db")

# Security
# Use environment variables in real deployments.
# Fallback defaults are kept for local/dev convenience.
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Pagination
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# Task priorities
PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3

VALID_PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]
VALID_STATUSES = ["todo", "in_progress", "done"]
