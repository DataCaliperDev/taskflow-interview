# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application configuration.

    Defaults are identical to the values that were previously hardcoded here, so
    with no `.env` present behavior is byte-for-byte unchanged. Any key can be
    overridden via an environment variable or a `.env` file (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    APP_NAME: str = "TaskFlow"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./taskflow.db"

    # Security
    SECRET_KEY: str = "supersecretkey123"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Pagination
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100


settings = Settings()

# Public, backwards-compatible config surface: existing
# `from app.config import SECRET_KEY` imports read these module-level names,
# which are sourced once from `settings` at import. Treat them as read-only.
APP_NAME = settings.APP_NAME
APP_VERSION = settings.APP_VERSION
DEBUG = settings.DEBUG
DATABASE_URL = settings.DATABASE_URL
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
DEFAULT_PAGE_SIZE = settings.DEFAULT_PAGE_SIZE
MAX_PAGE_SIZE = settings.MAX_PAGE_SIZE

# Domain constants — NOT deployment config, intentionally not env-configurable.
# Task priorities
PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3

VALID_PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]
VALID_STATUSES = ["todo", "in_progress", "done"]
