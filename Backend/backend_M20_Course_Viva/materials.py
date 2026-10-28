"""Adding material to a course, and taking it down (FR-20.5, 20.10, 20.11).

The same file added to the same course twice is one material (EC-20.10): the
second add returns the first, whatever the file was called.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlmodel import Session, select

from . import storage
from .db import FTS_TABLE
from .extract import MIME, extract
from .models import KINDS, VISIBILITIES, Campus, Course, Material, MaterialPage


class MaterialError(ValueError):
    """A request the library refuses, with a sentence a person can act on."""


@dataclass
class Added:
    material: Material
    created: bool


def _check(session: Session, course_id: str, kind: str, visibility: str, campus_id: str | None):
    if session.get(Course, course_id) is None:
        raise MaterialError("No such course.")
    if kind not in KINDS:
        raise MaterialError(f"Kind must be one of: {', '.join(KINDS)}.")
    if visibility not in VISIBILITIES:
        raise MaterialError("Visibility must be private or platform.")
    if campus_id and session.get(Campus, campus_id) is None:
        raise MaterialError("No such campus.")


def _existing(rows: list[Material], added_by: str) -> Material | None:
    """The material this upload already is: the uploader's own copy, else one
    shared with everyone (EC-20.10). Someone else's private or held copy is
    theirs alone and is never handed to another uploader (AC-20.3): this
    upload becomes a material of its own."""
    own = next((m for m in rows if m.added_by == added_by), None)
    if own is not None:
        if own.status == "removed":
            raise MaterialError("This file was taken down from this course.")
        return own
    if any(m.status == "removed" and m.visibility != "private" for m in rows):
        # EC-20.9: shared material taken down does not come back under
        # another name or another uploader. A private copy its owner removed
        # stops no one else.
        raise MaterialError("This file was taken down from this course.")
    return next((m for m in rows if m.status == "published" and m.visibility == "platform"), None)


def _settle(visibility: str, permission: str | None, by_curator: bool) -> str:
    """Shared with everyone needs a stated permission, or a curator (EC-20.8)."""
    if visibility == "platform" and not (permission or "").strip() and not by_curator:
        return "held"
    return visibility


def add_file(
    session: Session,
    *,
    course_id: str,
    data: bytes,
    filename: str,
    added_by: str,
    kind: str = "notes",
    title: str | None = None,
    unit: str | None = None,
    campus_id: str | None = None,
    visibility: str = "platform",
    permission: str | None = None,
    by_curator: bool = False,
) -> Added:
    _check(session, course_id, kind, visibility, campus_id)
    if not data:
        raise MaterialError("The file is empty.")
    digest = storage.sha256(data)
    same = session.exec(
        select(Material).where(Material.course_id == course_id, Material.sha256 == digest)
    ).all()
    existing = _existing(list(same), added_by)
    if existing is not None:
        return Added(existing, False)
    storage.save(data, filename)
    found = extract(data, filename)
    material = Material(
        course_id=course_id,
        campus_id=campus_id,
        title=(title or filename.rsplit(".", 1)[0]).strip()[:200] or "Untitled",
        kind=kind,
        unit=(unit or None),
        filename=filename[:255],
        mime=MIME.get(found.kind, MIME["unknown"]),
        bytes=len(data),
        sha256=digest,
        pages=len(found.pages),
        text_status=found.status,
        visibility=_settle(visibility, permission, by_curator),
        permission=(permission or "").strip()[:200] or None,
        added_by=added_by,
    )
    session.add(material)
    session.flush()
    for number, page_text in enumerate(found.pages, start=1):
        if not page_text.strip():
            continue
        session.add(MaterialPage(material_id=material.id, page=number, text=page_text))
        if found.status == "ok":
            session.exec(
                text(
                    f"INSERT INTO {FTS_TABLE}(text, material_id, page) VALUES (:t, :m, :p)"
                ).bindparams(t=page_text, m=material.id, p=number)
            )
    session.commit()
    session.refresh(material)
    return Added(material, True)


def add_link(
    session: Session,
    *,
    course_id: str,
    url: str,
    title: str,
    added_by: str,
    kind: str = "reference",
    unit: str | None = None,
    campus_id: str | None = None,
    visibility: str = "platform",
) -> Added:
    _check(session, course_id, kind, visibility, campus_id)
    if not url.startswith(("https://", "http://")):
        raise MaterialError("A link must start with http:// or https://.")
    same = session.exec(
        select(Material).where(Material.course_id == course_id, Material.url == url)
    ).all()
    existing = _existing(list(same), added_by)
    if existing is not None:
        return Added(existing, False)
    material = Material(
        course_id=course_id, campus_id=campus_id, title=title.strip()[:200] or url,
        kind=kind, unit=unit or None, url=url, text_status="link",
        visibility=visibility, added_by=added_by,
    )  # fmt: skip
    session.add(material)
    session.commit()
    session.refresh(material)
    return Added(material, True)


def approve(session: Session, material_id: str) -> Material | None:
    """A curator shares a held upload with everyone (EC-20.8)."""
    material = session.get(Material, material_id)
    if material is None or material.status != "published" or material.visibility != "held":
        return None
    material.visibility = "platform"
    session.commit()
    session.refresh(material)
    return material


def take_down(session: Session, material_id: str) -> Material | None:
    """Removed from every view and the search index (EC-20.9). The row stays,
    so the same file cannot quietly come back."""
    material = session.get(Material, material_id)
    if material is None:
        return None
    material.status = "removed"
    session.exec(text(f"DELETE FROM {FTS_TABLE} WHERE material_id = :m").bindparams(m=material_id))
    # ...and from every viva's question bank.
    from .bank import retire_material  # noqa: PLC0415

    retire_material(session, material_id)
    session.commit()
    return material
