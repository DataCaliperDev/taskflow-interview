"""Tests for the env-driven configuration (pydantic-settings).

These verify that the refactor preserves the original hardcoded defaults
(zero regression with no `.env` present) and that env overrides take effect.
"""

from app.config import (
    Settings,
    VALID_STATUSES,
    VALID_PRIORITIES,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_HIGH,
)


def test_settings_defaults_match_known_constants():
    s = Settings()
    assert s.APP_NAME == "TaskFlow"
    assert s.APP_VERSION == "1.0.0"
    assert s.DEBUG is True
    assert s.DATABASE_URL == "sqlite:///./taskflow.db"
    assert s.SECRET_KEY == "supersecretkey123"
    assert s.ALGORITHM == "HS256"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert s.DEFAULT_PAGE_SIZE == 10
    assert s.MAX_PAGE_SIZE == 100


def test_module_level_names_preserved():
    # Existing code does `from app.config import <NAME>`; these must stay importable.
    from app import config

    assert config.APP_NAME == "TaskFlow"
    assert config.SECRET_KEY == "supersecretkey123"
    assert config.DEFAULT_PAGE_SIZE == 10
    assert config.MAX_PAGE_SIZE == 100


def test_domain_constants_unchanged():
    assert VALID_STATUSES == ["todo", "in_progress", "done"]
    assert VALID_PRIORITIES == [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH]
    assert VALID_PRIORITIES == [1, 2, 3]


def test_constructor_override():
    s = Settings(SECRET_KEY="override")
    assert s.SECRET_KEY == "override"


def test_env_var_override(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "from-env")
    monkeypatch.setenv("MAX_PAGE_SIZE", "250")
    s = Settings()
    assert s.SECRET_KEY == "from-env"
    assert s.MAX_PAGE_SIZE == 250
