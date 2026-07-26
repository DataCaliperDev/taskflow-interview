# app/config.py
import os

# Application configuration
APP_NAME = "TaskFlow"
APP_VERSION = "1.0.0"
DEBUG = True

# Database
DATABASE_URL = "sqlite:///./taskflow.db"

# Security — intentionally hardcoded (Issue: should use env vars / pydantic-settings)
SECRET_KEY = "supersecretkey123"
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
