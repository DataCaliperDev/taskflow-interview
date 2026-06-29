import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, APP_VERSION, DEBUG
from app.database import init_db
from app.routers import auth, tasks, users

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("taskflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("TaskFlow started - database initialised.")
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="A simple task management API for teams.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(users.router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "version": APP_VERSION}
