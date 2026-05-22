# app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import APP_NAME, APP_VERSION
from app.database import init_db
from app.routers import auth, tasks, users

# Issue: no structured logging configured — print() used throughout instead
# Issue: no request/response middleware for logging or correlation IDs
# Issue: CORS is wide-open (all origins allowed), fine for dev but dangerous in prod


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    init_db()
    print("TaskFlow started — database initialised.")
    yield
    # Shutdown hooks (close pools, flush logs, etc.) would go here.


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="A simple task management API for teams.",
    lifespan=lifespan,
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


@app.get("/health")
def health_check():
    return {"status": "ok", "version": APP_VERSION}
