# tests/test_config.py

"""
Tests for environment-based configuration (app/config.py).
"""

import pytest

from app import config


def test_missing_secret_key_fails_with_clear_message(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(config.Settings, "model_config",
                        {**config.Settings.model_config, "env_file": None})

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config._load_settings()


def test_short_secret_key_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "too-short")

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        config._load_settings()


def test_values_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./other.db")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "5")

    settings = config._load_settings()

    assert settings.SECRET_KEY == "x" * 40
    assert settings.DATABASE_URL == "sqlite:///./other.db"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 5
