"""The viva's HTTP surface (spec §7): everything under /v1/vivas, a noun no
other module uses, so the platform shell routes it here unambiguously.

A viva is its student's. Nobody else can read it — not another student, not
the placement cell — and a viva on someone else's material uses only what the
library already lets the student see (`library.visible`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import bank, db, viva
from .db import get_session
from .library import Viewer, visible
from .models import Material, Question, Viva
from .router import curator, signed_in, viewer_of

router = APIRouter(prefix="/v1/vivas", tags=["viva"])
SessionDep = Annotated[Session, Depends(get_session)]


def _fail(error: viva.VivaError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.message)


def _prefetch(viva_id: str) -> None:
    """Bank the next pages while the student answers — in its own session,
    after the response is sent."""
    with Session(db.engine) as session:
        viva.prefetch(session, viva_id)


def _own(session: Session, viva_id: str, viewer: Viewer) -> Viva:
    row = session.get(Viva, viva_id)
    if row is None or row.student != viewer.subject:
        raise HTTPException(status_code=404, detail="No such viva.")
    return row


@router.get("/scope/{course_id}")
def scope(course_id: str, db_session: SessionDep, request: Request) -> dict:
    """What a viva on this course can be drawn from (FR-20.13), and what not."""
    viewer = viewer_of(request)
    try:
        found = viva.resolve_scope(db_session, viewer, course_id)
    except viva.VivaError as error:
        raise _fail(error) from error
    pages_by_material: dict[str, int] = {}
    for material_id, _page in found.pages:
        pages_by_material[material_id] = pages_by_material.get(material_id, 0) + 1
    banked: dict[str, int] = {}
    if found.materials:
        rows = db_session.exec(
            select(Question.material_id).where(
                Question.material_id.in_([m.id for m in found.materials]),
                Question.status.in_(("draft", "reviewed")),
            )
        ).all()
        for material_id in rows:
            banked[material_id] = banked.get(material_id, 0) + 1
    units = sorted({m.unit for m in found.materials if m.unit}, key=viva._unit_order)
    return {
        "course": {"id": found.course.id, "code": found.course.code, "title": found.course.title},
        "materials": [
            {
                "id": m.id,
                "title": m.title,
                "kind": m.kind,
                "unit": m.unit,
                "pages": m.pages,
                "usable_pages": pages_by_material.get(m.id, 0),
                "questions": banked.get(m.id, 0),
                # A long document is taken ten pages at a time (bank.PART_PAGES).
                "parts": viva.parts(db_session, m, viewer.subject)
                if m.pages > bank.PART_PAGES
                else [],
            }
            for m in found.materials
        ],
        "units": units,
        "excluded": found.excluded,
        "ready": bool(found.pages),
    }


class StartIn(BaseModel):
    course_id: str
    material_ids: list[str] | None = None
    unit: str | None = None
    #: {material_id: [first page, last page]}
    pages: dict[str, list[int]] | None = None
    mode: str = "typed"
    #: "lab" walks an experiment's steps (FR-20.19); "course" the material.
    style: str = "course"
    questions: int = Field(
        default=viva.DEFAULT_QUESTIONS, ge=viva.MIN_QUESTIONS, le=viva.MAX_QUESTIONS
    )


@router.post("", status_code=201)
def start(
    body: StartIn, background: BackgroundTasks, db_session: SessionDep, request: Request
) -> dict:
    viewer = signed_in(request)
    for span in (body.pages or {}).values():
        if len(span) != 2 or span[0] < 1 or span[1] < span[0]:
            raise HTTPException(status_code=422, detail="A page range is [first, last], from 1.")
    try:
        row = viva.start(
            db_session,
            viewer,
            body.course_id,
            material_ids=body.material_ids,
            unit=body.unit,
            pages=body.pages,
            mode=body.mode,
            questions=body.questions,
            style=body.style,
        )
    except viva.VivaError as error:
        raise _fail(error) from error
    background.add_task(_prefetch, row.id)
    return viva.state(db_session, row)


@router.get("")
def mine(db_session: SessionDep, request: Request) -> list[dict]:
    viewer = signed_in(request)
    return viva.history(db_session, viewer.subject)


@router.get("/{viva_id}")
def get(viva_id: str, db_session: SessionDep, request: Request) -> dict:
    return viva.state(db_session, _own(db_session, viva_id, signed_in(request)))


class AnswerIn(BaseModel):
    text: str = Field(max_length=8000)
    #: What the client measured: {"silence_ms", "duration_ms", "spoken"}.
    timing: dict | None = None


@router.post("/{viva_id}/answer")
def answer(
    viva_id: str,
    body: AnswerIn,
    background: BackgroundTasks,
    db_session: SessionDep,
    request: Request,
) -> dict:
    row = _own(db_session, viva_id, signed_in(request))
    with viva.lock(viva_id):
        db_session.refresh(row)
        try:
            row = viva.answer(db_session, row, body.text, body.timing)
        except viva.VivaError as error:
            raise _fail(error) from error
    background.add_task(_prefetch, row.id)
    return viva.state(db_session, row)


@router.post("/{viva_id}/hint")
def hint(viva_id: str, db_session: SessionDep, request: Request) -> dict:
    row = _own(db_session, viva_id, signed_in(request))
    with viva.lock(viva_id):
        db_session.refresh(row)
        try:
            row = viva.hint(db_session, row)
        except viva.VivaError as error:
            raise _fail(error) from error
    return viva.state(db_session, row)


@router.post("/{viva_id}/end")
def end(viva_id: str, db_session: SessionDep, request: Request) -> dict:
    row = _own(db_session, viva_id, signed_in(request))
    with viva.lock(viva_id):
        db_session.refresh(row)
        row = viva.end(db_session, row)
    return viva.state(db_session, row)


@router.get("/{viva_id}/report")
def report(viva_id: str, db_session: SessionDep, request: Request) -> dict:
    return viva.report(db_session, _own(db_session, viva_id, signed_in(request)))


# ── The bank, reviewable (FR-20.14) ─────────────────────────────────────────


def _question_out(q: Question) -> dict:
    return {
        "id": q.id,
        "material_id": q.material_id,
        "page": q.page,
        "family": q.family,
        "answer_length": q.answer_length,
        "text": q.text,
        "quote": q.quote,
        "answer_points": q.answer_points,
        "hint": q.hint,
        "difficulty": q.difficulty,
        "status": q.status,
        "written_by": q.generated_by,
        # Written under an older bank prompt: the page is banked again when a
        # viva next reaches it, and this one is retired then.
        "current": q.prompt_version == bank.PROMPT_VERSION,
    }


@router.get("/bank/{material_id}")
def bank_of(
    material_id: str, db_session: SessionDep, request: Request, retired: bool = False
) -> dict:
    """A material's questions — readable by anyone who can read the material;
    with `retired`, the retired ones too, so a retirement can be undone."""
    viewer = viewer_of(request)
    material = db_session.exec(
        select(Material).where(Material.id == material_id, visible(viewer))
    ).first()
    if material is None:
        raise HTTPException(status_code=404, detail="No such material.")
    query = select(Question).where(Question.material_id == material_id)
    if not retired:
        query = query.where(Question.status != "retired")
    rows = db_session.exec(query.order_by(Question.page, Question.span_start)).all()
    pages = db_session.exec(
        select(bank.BankPage).where(bank.BankPage.material_id == material_id)
    ).all()
    return {
        "material": {"id": material.id, "title": material.title, "pages": material.pages},
        "pages_banked": sum(1 for p in pages if bank.current(p)),
        # Banked pages that gave no question, and why ("too short to examine").
        "skipped": [
            {"page": p.page, "why": p.reason or ""}
            for p in sorted(pages, key=lambda p: p.page)
            if bank.current(p) and p.questions == 0
        ],
        "questions": [_question_out(q) for q in rows],
    }


class ReviewIn(BaseModel):
    status: str  # reviewed | retired | draft


@router.post("/bank/questions/{question_id}")
def review(question_id: str, body: ReviewIn, db_session: SessionDep, request: Request) -> dict:
    """The placement cell marks a question reviewed, or retires it."""
    curator(request)
    if body.status not in ("reviewed", "retired", "draft"):
        raise HTTPException(status_code=422, detail="Status is reviewed, retired or draft.")
    question = db_session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="No such question.")
    question.status = body.status
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return _question_out(question)
