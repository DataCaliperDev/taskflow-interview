# app/config.py
import os

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")
    secret_key: str = Field(alias="SECRET_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Application configuration
APP_NAME = "TaskFlow"
APP_VERSION = "1.0.0"
DEBUG = True

# Database
DATABASE_URL = settings.database_url

# Security — intentionally hardcoded (Issue: should use env vars / pydantic-settings)
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Pagination
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# Task priorities
PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3

VALID_PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]
VALID_STATUSES = ["todo", "in_progress", "done"]
