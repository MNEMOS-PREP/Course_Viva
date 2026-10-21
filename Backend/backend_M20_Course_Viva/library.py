"""What the library shows: the tree, a campus, a programme, a course, search,
coverage. Read-only; every query respects who is looking (AC-20.3)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, false, func, or_, text
from sqlmodel import Session, select

from .db import FTS_TABLE
from .models import Campus, Course, Curriculum, Institution, Material, Offering, Programme


@dataclass(frozen=True)
class Viewer:
    """Who is looking. `subject` None is someone not signed in."""

    subject: str | None = None
    admin: bool = False


def visible(viewer: Viewer):
    """The one visibility rule: published, and either shared or the viewer's own."""
    rule = Material.status == "published"
    if viewer.admin:
        return rule
    own = Material.added_by == viewer.subject if viewer.subject else false()
    return rule & or_(Material.visibility == "platform", own)


def _material_counts(session: Session, viewer: Viewer, course_ids: list[str]) -> dict[str, int]:
    if not course_ids:
        return {}
    rows = session.exec(
        select(Material.course_id, func.count())
        .where(Material.course_id.in_(course_ids), visible(viewer))
        .group_by(Material.course_id)
    )
    return dict(rows.all())


def latest_parsed(session: Session, programme_id: str) -> Curriculum | None:
    curricula = session.exec(
        select(Curriculum)
        .where(Curriculum.programme_id == programme_id)
        .order_by(Curriculum.year.desc())
    ).all()
    return next((c for c in curricula if c.status == "parsed"), curricula[0] if curricula else None)


def tree(session: Session) -> dict:
    inst = session.exec(select(Institution)).first()
    campuses = session.exec(select(Campus).order_by(Campus.position)).all()
    counts = dict(
        session.exec(select(Offering.campus_id, func.count()).group_by(Offering.campus_id)).all()
    )
    return {
        "institution": inst.model_dump() if inst else None,
        "campuses": [{**c.model_dump(), "programmes": counts.get(c.id, 0)} for c in campuses],
    }


def campus(session: Session, campus_id: str, viewer: Viewer) -> dict | None:
    row = session.get(Campus, campus_id)
    if row is None:
        return None
    programmes = session.exec(
        select(Programme)
        .join(Offering, Offering.programme_id == Programme.id)
        .where(Offering.campus_id == campus_id)
        .order_by(Programme.school, Programme.name)
    ).all()
    out = []
    for prog in programmes:
        cur = latest_parsed(session, prog.id)
        course_ids = (
            session.exec(select(Course.id).where(Course.curriculum_id == cur.id)).all()
            if cur
            else []
        )
        materials = sum(_material_counts(session, viewer, list(course_ids)).values())
        out.append(
            {
                **prog.model_dump(),
                "curriculum_year": cur.year if cur else None,
                "curriculum_status": cur.status if cur else None,
                "courses": len(course_ids),
                "materials": materials,
            }
        )
    return {"campus": row.model_dump(), "programmes": out}


def programme(
    session: Session, programme_id: str, viewer: Viewer, year: int | None = None
) -> dict | None:
    prog = session.get(Programme, programme_id)
    if prog is None:
        return None
    curricula = session.exec(
        select(Curriculum)
        .where(Curriculum.programme_id == programme_id)
        .order_by(Curriculum.year.desc())
    ).all()
    chosen = (
        next((c for c in curricula if c.year == year), None)
        if year
        else latest_parsed(session, programme_id)
    )
    offered = session.exec(
        select(Campus)
        .join(Offering, Offering.campus_id == Campus.id)
        .where(Offering.programme_id == programme_id)
        .order_by(Campus.position)
    ).all()
    semesters: dict[int, list[dict]] = {}
    electives: dict[str, list[dict]] = {}
    if chosen is not None:
        courses = session.exec(
            select(Course).where(Course.curriculum_id == chosen.id).order_by(Course.code)
        ).all()
        counts = _material_counts(session, viewer, [c.id for c in courses])
        for course in courses:
            row = {
                "id": course.id, "code": course.code, "title": course.title,
                "credits": course.credits, "ltp": course.ltp, "category": course.category,
                "has_syllabus": bool(course.syllabus), "materials": counts.get(course.id, 0),
            }  # fmt: skip
            if course.semester is not None:
                semesters.setdefault(course.semester, []).append(row)
            else:
                electives.setdefault(course.basket or "Electives", []).append(row)
    return {
        "programme": prog.model_dump(),
        "campuses": [c.model_dump() for c in offered],
        "curricula": [
            {"id": c.id, "year": c.year, "status": c.status, "documents": c.documents}
            for c in curricula
        ],
        "curriculum": (
            {
                "id": chosen.id,
                "year": chosen.year,
                "status": chosen.status,
                "documents": chosen.documents,
                "parsed_from": chosen.parsed_from,
                "slots": chosen.slots,
            }  # fmt: skip
            if chosen
            else None
        ),
        "semesters": [{"number": n, "courses": semesters[n]} for n in sorted(semesters)],
        "electives": [{"name": name, "courses": rows} for name, rows in sorted(electives.items())],
    }


def course(session: Session, course_id: str, viewer: Viewer) -> dict | None:
    row = session.get(Course, course_id)
    if row is None:
        return None
    cur = session.get(Curriculum, row.curriculum_id)
    prog = session.get(Programme, cur.programme_id) if cur else None
    materials = session.exec(
        select(Material)
        .where(Material.course_id == course_id, visible(viewer))
        .order_by(Material.kind, Material.unit, Material.created_at)
    ).all()
    return {
        "course": row.model_dump(),
        "curriculum": (
            {
                "id": cur.id,
                "year": cur.year,
                "documents": cur.documents,
                # The PDF the syllabus and its page number were read from.
                "parsed_from": cur.parsed_from,
            }  # fmt: skip
            if cur
            else None
        ),
        "programme": prog.model_dump() if prog else None,
        "materials": [_material_out(m) for m in materials],
    }


def _material_out(m: Material) -> dict:
    data = m.model_dump(exclude={"sha256"})
    data["created_at"] = m.created_at.isoformat()
    return data


def _offered(session: Session) -> dict[str, list[str]]:
    """Programme id → the campuses that run it, in campus order."""
    out: dict[str, list[str]] = {}
    rows = session.exec(
        select(Offering.programme_id, Offering.campus_id)
        .join(Campus, Campus.id == Offering.campus_id)
        .order_by(Campus.position)
    )
    for programme_id, campus_id in rows.all():
        out.setdefault(programme_id, []).append(campus_id)
    return out


def search(
    session: Session,
    query: str,
    viewer: Viewer,
    *,
    programme_id: str | None = None,
    semester: int | None = None,
    limit: int = 30,
) -> dict:
    """Courses whose code, title or syllabus match, and pages of material that do."""
    words = [w for w in "".join(ch if ch.isalnum() else " " for ch in query).split() if w]
    if not words:
        return {"courses": [], "pages": []}
    offered = _offered(session)
    like = f"%{' '.join(words)}%"
    # A code or title match is the course asked for; a syllabus match only
    # mentions it. Ranked so the second kind never crowds out the first.
    match_rank = case((Course.code.ilike(like), 0), (Course.title.ilike(like), 1), else_=2)
    course_q = (
        select(Course, Curriculum, Programme, match_rank)
        .join(Curriculum, Curriculum.id == Course.curriculum_id)
        .join(Programme, Programme.id == Curriculum.programme_id)
        .where(or_(Course.code.ilike(like), Course.title.ilike(like), Course.syllabus.ilike(like)))
        .order_by(match_rank, Course.semester.is_(None), Programme.short, Course.code)
    )
    if programme_id:
        course_q = course_q.where(Curriculum.programme_id == programme_id)
    if semester is not None:
        course_q = course_q.where(Course.semester == semester)
    courses = [
        {
            "id": c.id,
            "code": c.code,
            "title": c.title,
            "semester": c.semester,
            "programme_id": cur.programme_id,
            "programme": prog.name,
            "short": prog.short,
            "year": cur.year,
            "campuses": offered.get(cur.programme_id, []),
            "match": ("code", "title", "syllabus")[rank],
        }  # fmt: skip
        for c, cur, prog, rank in session.exec(course_q.limit(limit)).all()
    ]
    # FTS5: each word a prefix term, all required.
    match = " ".join(f'"{w}"*' for w in words)
    rows = session.exec(
        text(
            f"SELECT material_id, page, snippet({FTS_TABLE}, 0, '[', ']', '…', 14) "
            f"FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH :m ORDER BY rank LIMIT :n"
        ).bindparams(m=match, n=limit * 3)
    ).all()
    pages = []
    for material_id, page, snippet in rows:
        material = session.get(Material, material_id)
        if (
            material is None
            or not session.exec(
                select(Material.id).where(Material.id == material_id, visible(viewer))
            ).first()
        ):
            continue
        course_row = session.get(Course, material.course_id)
        cur = session.get(Curriculum, course_row.curriculum_id) if course_row else None
        if programme_id and (cur is None or cur.programme_id != programme_id):
            continue
        if semester is not None and (course_row is None or course_row.semester != semester):
            continue
        pages.append(
            {
                "material_id": material_id,
                "title": material.title,
                "kind": material.kind,
                "page": int(page),
                "snippet": snippet,
                "course_id": material.course_id,
                "course": f"{course_row.code} {course_row.title}" if course_row else "",
                "campuses": offered.get(cur.programme_id, []) if cur else [],
            }  # fmt: skip
        )
        if len(pages) >= limit:
            break
    return {"courses": courses, "pages": pages}


def coverage(session: Session, viewer: Viewer) -> list[dict]:
    """Per campus and programme: courses, and how many have any material (FR-20.12)."""
    out = []
    for camp in session.exec(select(Campus).order_by(Campus.position)).all():
        for prog in campus(session, camp.id, viewer)["programmes"]:
            cur = latest_parsed(session, prog["id"])
            course_ids = (
                list(session.exec(select(Course.id).where(Course.curriculum_id == cur.id)).all())
                if cur
                else []
            )
            with_material = len(_material_counts(session, viewer, course_ids))
            out.append(
                {
                    "campus": camp.name,
                    "campus_id": camp.id,
                    "programme_id": prog["id"],
                    "programme": prog["name"],
                    "short": prog["short"],
                    "year": prog["curriculum_year"],
                    "courses": len(course_ids),
                    "with_material": with_material,
                }  # fmt: skip
            )
    return out
