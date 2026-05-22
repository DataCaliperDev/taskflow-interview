# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str

    app_name: str = "TaskFlow"
    app_version: str = "1.0.0"
    debug: bool = True

    database_url: str = "sqlite:///./taskflow.db"

    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


settings = Settings()


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3

VALID_PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]
VALID_STATUSES = ["todo", "in_progress", "done"]
