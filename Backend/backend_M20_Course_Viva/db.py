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
    _owner_unique(target)
    SQLModel.metadata.create_all(target)
    _added_columns(target)
    with target.begin() as conn:
        conn.execute(
            text(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} "
                "USING fts5(text, material_id UNINDEXED, page UNINDEXED, tokenize='unicode61')"
            )
        )


#: Columns added to a table after it shipped: (table, column, its DDL).
#: `create_all` makes missing tables, never missing columns.
ADDED_COLUMNS = (
    # 2026-10-28: a viva asks short-answer and long-answer questions.
    ("question", "answer_length", "VARCHAR NOT NULL DEFAULT 'long'"),
    # 2026-10-28: a page that is only a picture is read by a vision model.
    ("materialpage", "read_by", "VARCHAR"),
)


def _added_columns(target) -> None:
    with target.begin() as conn:
        for table, column, ddl in ADDED_COLUMNS:
            have = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if have and column not in have:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


#: The constraint a material table made before 2026-10-26 carries.
_OLD_UNIQUE = "CONSTRAINT uq_material_course_hash UNIQUE"


def _owner_unique(target) -> None:
    """2026-10-26: a material is unique per course, file AND uploader (it was
    per course and file, which handed one student's private copy to the next
    to upload the same file). SQLite cannot change a constraint in place, so a
    table made before is rebuilt the way its docs give, its rows kept."""
    from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: PLC0415

    from .models import Material  # noqa: PLC0415

    with target.connect() as conn:
        if conn.dialect.name != "sqlite":
            return
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'material'")
        ).scalar()
        if not ddl or _OLD_UNIQUE not in ddl:
            return
        table = Material.__table__
        columns = ", ".join(column.name for column in table.columns)
        create = str(CreateTable(table).compile(conn)).replace(
            "CREATE TABLE material ", "CREATE TABLE material_new ", 1
        )
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")  # material_page points here
        try:
            conn.exec_driver_sql("DROP TABLE IF EXISTS material_new")
            conn.exec_driver_sql(create)
            conn.exec_driver_sql(
                f"INSERT INTO material_new ({columns}) SELECT {columns} FROM material"
            )
            conn.exec_driver_sql("DROP TABLE material")
            conn.exec_driver_sql("ALTER TABLE material_new RENAME TO material")
            for index in table.indexes:
                conn.execute(CreateIndex(index))
            conn.commit()
        finally:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
