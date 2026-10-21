"""The database: SQLite locally (WAL, so reads never wait on an import), with
a full-text index over every page of material (FR-20.9)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

from . import config

FTS_TABLE = "material_fts"


def make_engine(url: str | None = None):
    url = url or config.DATABASE_URL
    sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if sqlite else {})
    if sqlite:

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi, _record):  # noqa: ANN001
            cursor = dbapi.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


engine = make_engine()


def init(target=None) -> None:
    """Create the tables and the page index. Idempotent."""
    from . import models  # noqa: F401 - registers the tables

    target = target or engine
    SQLModel.metadata.create_all(target)
    with target.begin() as conn:
        conn.execute(
            text(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} "
                "USING fts5(text, material_id UNINDEXED, page UNINDEXED, tokenize='unicode61')"
            )
        )


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
