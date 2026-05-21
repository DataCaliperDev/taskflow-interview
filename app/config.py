"""Application settings -- UC-4: Configuration & Secrets.

The original config kept the signing secret and database location as
hardcoded constants in source. UC-4 moves both into the environment so
deployments rotate the secret without a code change, and so the secret
never lives in the repository.

The signing secret is required and has no default: an unconfigured
deployment fails to boot rather than running on a known-bad value.
``.env`` is gitignored; ``.env.example`` documents every key a
deployer needs to set.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read environment first, then ``.env`` in the working directory.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "TaskFlow"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite:///./taskflow.db"

    # Token-signing secret. Required; no default. The 16-character
    # minimum is a sanity guard, not a strength claim -- callers should
    # supply something generated, not typed.
    SECRET_KEY: str = Field(..., min_length=16)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Page bounds for the catalog endpoints (UC-6). 100 is the hard
    # cap; out-of-range page sizes are rejected at the request boundary.
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100


settings = Settings()