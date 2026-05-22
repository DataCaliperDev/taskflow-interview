# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import auth, tasks, users

# Issue: no structured logging configured — print() used throughout instead
# Issue: no request/response middleware for logging or correlation IDs
# Issue: CORS is wide-open (all origins allowed), fine for dev but dangerous in prod

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A simple task management API for teams.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(users.router)


@app.on_event("startup")
def on_startup():
    init_db()
    print("TaskFlow started — database initialised.")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}
