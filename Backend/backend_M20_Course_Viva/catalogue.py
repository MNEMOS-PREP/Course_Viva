"""Load the synced catalogue (packages/catalogue/amrita.json) into the database.

Upserts by id, so re-loading a newer sync updates names, campuses and courses
without touching material already added to a course: a course's id is its
curriculum and its code, which a re-sync does not change.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlmodel import Session, select

from . import config
from .models import Campus, Course, Curriculum, Institution, Meta, Offering, Programme

log = logging.getLogger(__name__)
LOADED_KEY = "catalogue_fetched_at"


def _upsert(session: Session, model, **values):
    """Insert or update by the table's own primary key."""
    names = [column.name for column in model.__table__.primary_key.columns]
    key = tuple(values[name] for name in names)
    row = session.get(model, key if len(key) > 1 else key[0])
    if row is None:
        row = model(**values)
        session.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
    return row


def course_id(curriculum_id: str, code: str) -> str:
    return f"{curriculum_id}:{code}"


def load(session: Session, data: dict) -> dict[str, int]:
    """Upsert everything in `data`. Returns counts for a log line."""
    inst = data["institution"]
    _upsert(session, Institution, id=inst["id"], name=inst["name"], display=inst["display"])
    for position, campus in enumerate(data["campuses"]):
        _upsert(
            session, Campus, id=campus["id"], institution_id=inst["id"],
            name=campus["name"], position=position,
        )  # fmt: skip
    counts = {"programmes": 0, "offerings": 0, "curricula": 0, "courses": 0}
    campus_ids = {c["id"] for c in data["campuses"]}
    for prog in data["programmes"]:
        _upsert(
            session, Programme, id=prog["id"], institution_id=inst["id"], degree=prog["degree"],
            name=prog["name"], short=prog["short"], school=prog["school"],
            source_url=prog.get("source_url"), also_at=prog.get("also_at", []),
        )  # fmt: skip
        counts["programmes"] += 1
        existing = {
            o.campus_id: o
            for o in session.exec(select(Offering).where(Offering.programme_id == prog["id"]))
        }
        for campus_id in prog["campuses"]:
            if campus_id in campus_ids and campus_id not in existing:
                session.add(
                    Offering(
                        campus_id=campus_id,
                        programme_id=prog["id"],
                        source_url=prog.get("source_url"),
                    )
                )
            counts["offerings"] += 1
        for gone in set(existing) - set(prog["campuses"]):
            # The programme page no longer lists this campus.
            session.delete(existing[gone])
        for cur in prog["curricula"]:
            cid = f"{prog['id']}-{cur['year']}"
            _upsert(
                session, Curriculum, id=cid, programme_id=prog["id"], year=cur["year"],
                documents=cur.get("documents", []), status=cur.get("status", "listed"),
                parsed_from=cur.get("parsed_from"), warnings=cur.get("warnings", []),
                slots={str(s["number"]): s.get("slots", []) for s in cur.get("semesters", [])},
            )  # fmt: skip
            counts["curricula"] += 1
            for sem in cur.get("semesters", []):
                for c in sem["courses"]:
                    _course(session, cid, c, semester=sem["number"])
                    counts["courses"] += 1
            for basket in cur.get("electives", []):
                for c in basket["courses"]:
                    _course(session, cid, c, basket=basket["name"])
                    counts["courses"] += 1
    _upsert(session, Meta, key=LOADED_KEY, value=data.get("fetched_at", ""))
    session.commit()
    return counts


def _course(session: Session, cid: str, c: dict, *, semester=None, basket=None) -> None:
    _upsert(
        session, Course, id=course_id(cid, c["code"]), curriculum_id=cid, code=c["code"],
        title=c["title"], semester=semester, basket=basket, category=c.get("category"),
        ltp=c.get("ltp"), credits=c.get("credits"), syllabus=c.get("syllabus"),
        syllabus_page=c.get("syllabus_page"),
    )  # fmt: skip


def load_if_newer(session: Session, path: Path | None = None) -> dict[str, int] | None:
    """At start: load the catalogue file if the database holds an older one."""
    path = path or config.CATALOGUE_FILE
    if not path.exists():
        log.warning("no catalogue at %s; run jobs.sync_catalogue", path)
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    held = session.get(Meta, LOADED_KEY)
    if held is not None and held.value == data.get("fetched_at"):
        return None
    counts = load(session, data)
    log.info("catalogue loaded", extra=counts)
    return counts
