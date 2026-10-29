from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.jobs import router as jobs_router
from app.api.artifacts import router as artifacts_router
from app.api.health import router as health_router
from app.api.videos import router as videos_router
from app.config import FRONTEND_ORIGIN
from app.database import Base, engine
from app import models  # noqa: F401 - register SQLAlchemy models before create_all


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="SceneTrace API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router, prefix="/api")
app.include_router(videos_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
