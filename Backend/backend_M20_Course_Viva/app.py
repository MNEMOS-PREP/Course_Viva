"""M20 — Course Viva, on its reserved port 8120 (PORTS.txt).

    .venv\\Scripts\\python -m uvicorn backend_M20_Course_Viva.app:app --port 8120

At start the database is created and the synced catalogue loaded into it, if it
is newer than what the database holds.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ai_core.dependencies import DependencyRegistry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlmodel import Session, select

from . import catalogue, config, db
from .models import Course, Material, Meta, Programme
from .router import router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    with Session(db.engine) as session:
        catalogue.load_if_newer(session)
    yield


app = FastAPI(title="M20 — Course Viva", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5220", "http://127.0.0.1:5220", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    with Session(db.engine) as session:
        held = session.get(Meta, catalogue.LOADED_KEY)
        return {
            "status": "ok",
            "module": "M20",
            "catalogue_fetched_at": held.value if held else None,
            "programmes": session.exec(select(func.count()).select_from(Programme)).one(),
            "courses": session.exec(select(func.count()).select_from(Course)).one(),
            "materials": session.exec(select(func.count()).select_from(Material)).one(),
        }


@app.get("/v1/deps", tags=["ops"])
def deps() -> list:
    """What M20 degrades without (the platform's shape)."""
    if not config.MODULE_JSON.exists():
        return []
    return DependencyRegistry.from_manifest(config.MODULE_JSON).statuses()
