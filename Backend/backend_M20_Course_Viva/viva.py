"""A viva on a student's own material (FR-20.13, 20.15, 20.16, 20.18; spec §6.4).

    scope -> warm-up -> question -> answer -> marked
                                   correct ...................... next question
                                   partial ....... follow-up ---> marked again
                                   wrong / blank . hint --------> marked again
                                   still not right .............. taught, with the page

── Not an interview (Trap 5) ──────────────────────────────────────────────────

No "tell me about yourself", no panel, no hiring rubric. An examiner, one
document's worth of questions at a time, and the help an examiner gives: a
follow-up on a partial answer, a hint on a blank, and on a second miss the
answer itself, taught, with the page to reread.

── Where the model is, and is not ─────────────────────────────────────────────

The examiner's words are written here, by rule. Questions, their follow-ups
and their hints come from the bank (`bank.py`), written once per page. The only
model call a viva makes on its own is marking an answer (`marking.py`). The
warm-up is not marked — it is the question an examiner always opens with — and
while the student answers it the first pages of the scope are banked, so the
first real question is ready when they finish.

── The page is shown after the answer, never before (spec §2.3) ───────────────

A question's citation is in the state only once its item is closed, and in the
teaching line that closes it.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from . import bank, marking, speaking
from .library import Viewer, _unit_order, visible
from .models import Course, Material, MaterialPage, Question, Viva, VivaTurn

#: Questions after the warm-up: the default, and what a viva may ask for.
DEFAULT_QUESTIONS = 6
MIN_QUESTIONS, MAX_QUESTIONS = 3, 12
#: Pages visited per question asked: room to skip a page with nothing to ask.
PAGES_PER_QUESTION = 2
#: Pages banked while the student answers, ahead of where the viva is.
PREFETCH = 2
#: Pages with questions weighed together when choosing the next one.
LENGTH_WINDOW = 2
#: Pages banked while a request waits, at most, before the viva says it has run out.
BANK_ON_DEMAND = 3

#: The examiners are the platform's academic interviewers (M06's personas):
#: M11 already casts each a voice, and has their photograph and, for most, a
#: 3D head — so a viva is taken by a person the student can see and hear,
#: not a text box. `voice_id` is M11's cast key (voices/cast.json); the room
#: speaks in it, and in the browser's own voice when M11 is not running.
EXAMINERS = (
    {
        "id": "professor",
        "name": "Dr. Raghavan",
        "title": "Professor",
        "voice_id": "indictts-012635",
    },
    {
        "id": "os_narayan",
        "name": "Dr. Narayan",
        "title": "Associate Professor",
        "voice_id": "indictts-128877",
    },
    {
        "id": "proj_murthy",
        "name": "Professor Murthy",
        "title": "Professor of Computer Science",
        "voice_id": "indictts-012635",
    },
    {
        "id": "ml_deshpande",
        "name": "Dr. Deshpande",
        "title": "Research Scientist",
        "voice_id": "indictts-017689",
    },
)

#: Why a material in scope cannot be questioned on (Trap 7, EC-20.5).
EXCLUDED_WHY = {
    "no_text": "a scan or an image: there is no text to ask from yet",
    "failed": "it could not be read",
    "link": "a link: there is nothing here to read",
    "pending": "it is still being read",
}


class VivaError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ── Scope (FR-20.13) ────────────────────────────────────────────────────────


@dataclass
class Scope:
    course: Course
    label: str
    materials: list[Material]
    excluded: list[dict[str, str]]
    #: Every page with enough text to examine, in reading order.
    pages: list[tuple[str, int]]


def resolve_scope(
    session: Session,
    viewer: Viewer,
    course_id: str,
    *,
    material_ids: list[str] | None = None,
    unit: str | None = None,
    pages: dict[str, list[int]] | None = None,
) -> Scope:
    course = session.get(Course, course_id)
    if course is None:
        raise VivaError(404, "No such course.")
    rows = list(
        session.exec(select(Material).where(Material.course_id == course_id, visible(viewer))).all()
    )
    if material_ids:
        wanted = set(material_ids)
        rows = [m for m in rows if m.id in wanted]
        if len(rows) != len(wanted):
            raise VivaError(
                404, "Some of that material is not in this course, or not yours to use."
            )
    if unit:
        rows = [m for m in rows if (m.unit or "").casefold() == unit.casefold()]
    rows.sort(key=lambda m: (_unit_order(m.unit), m.kind != "lab_manual", m.created_at))

    usable, excluded = [], []
    for material in rows:
        if material.text_status == "ok":
            usable.append(material)
        else:
            why = EXCLUDED_WHY.get(material.text_status, "it has no text")
            excluded.append({"material_id": material.id, "title": material.title, "why": why})

    refs: list[tuple[str, int]] = []
    for material in usable:
        lo, hi = (pages or {}).get(material.id, [1, 10**6])[:2] if pages else (1, 10**6)
        lengths = session.exec(
            select(MaterialPage.page, func.length(MaterialPage.text))
            .where(MaterialPage.material_id == material.id)
            .order_by(MaterialPage.page)
        ).all()
        refs += [
            (material.id, page)
            for page, length in lengths
            if lo <= page <= hi and (length or 0) >= bank.MIN_PAGE_CHARS
        ]

    if unit:
        label = unit
    elif len(usable) == 1:
        # A lab manual filed under "Lab 6" is "Lab 6", whatever the file was called.
        label = usable[0].unit or usable[0].title
    else:
        label = course.title
    return Scope(course, label, usable, excluded, refs)


def _visit_order(refs: list[tuple[str, int]], target: int, seed: str) -> list[list]:
    """Which pages the viva walks, in reading order: all of a short scope, an
    even spread of a long one (a viva on a 300-page reader should not spend
    six questions on chapter one)."""
    want = max(target * PAGES_PER_QUESTION, target + 2)
    if len(refs) <= want:
        chosen = refs
    else:
        step = len(refs) / want
        offset = random.Random(seed).random() * step
        chosen = [refs[min(len(refs) - 1, int(offset + i * step))] for i in range(want)]
        chosen = list(dict.fromkeys(chosen))
    return [[m, p] for m, p in chosen]


# ── Turns ───────────────────────────────────────────────────────────────────


def _turns(session: Session, viva_id: str) -> list[VivaTurn]:
    return list(
        session.exec(select(VivaTurn).where(VivaTurn.viva_id == viva_id).order_by(VivaTurn.seq))
    )


def _say(
    session: Session,
    viva: Viva,
    role: str,
    kind: str,
    text: str,
    item: int,
    *,
    question_id: str | None = None,
    timing: dict | None = None,
) -> VivaTurn:
    seq = session.exec(select(func.max(VivaTurn.seq)).where(VivaTurn.viva_id == viva.id)).one() or 0
    turn = VivaTurn(
        viva_id=viva.id,
        seq=seq + 1,
        role=role,
        kind=kind,
        text=text,
        item=item,
        question_id=question_id,
        timing=timing,
    )
    session.add(turn)
    session.flush()
    return turn


def _pick(viva: Viva, options: list[str], salt: int) -> str:
    """A line from `options`, varied but stable for this viva."""
    return options[random.Random(f"{viva.id}:{salt}").randrange(len(options))]


def _examiner(viva: Viva) -> dict[str, str]:
    return next((e for e in EXAMINERS if e["id"] == viva.examiner), EXAMINERS[0])


def _cite(session: Session, question: Question) -> dict[str, Any]:
    material = session.get(Material, question.material_id)
    return {
        "material_id": question.material_id,
        "title": material.title if material else "",
        "kind": material.kind if material else "",
        "page": question.page,
        "quote": question.quote,
        "span_start": question.span_start,
        "span_end": question.span_end,
    }


# ── Choosing the next question ──────────────────────────────────────────────


def style_of(viva: Viva) -> str:
    return (viva.scope or {}).get("style") or "course"


def lab_stage(question: Question) -> int:
    """Where a question falls in a lab viva's walk (FR-20.19): after every
    step when its family is in none."""
    for index, (_name, families) in enumerate(bank.LAB_STAGES):
        if question.family in families:
            return index
    return len(bank.LAB_STAGES)


def stage_name(question: Question) -> str | None:
    index = lab_stage(question)
    if index < len(bank.LAB_STAGES):
        return bank.LAB_STAGES[index][0]
    return "aim" if question.family == "aim" else None


def _asked_before(session: Session, student: str, exclude_viva: str) -> set[str]:
    rows = session.exec(
        select(VivaTurn.question_id)
        .join(Viva, Viva.id == VivaTurn.viva_id)
        .where(Viva.student == student, Viva.id != exclude_viva, VivaTurn.question_id.is_not(None))
    ).all()
    return {r for r in rows if r}


def _next_question(session: Session, viva: Viva, *, llm: Any = None) -> Question | None:
    """The next question: the next page of the scope that has one not yet asked
    here, a different family from the last, about as hard as the viva is by
    now, and not one this student was asked in an earlier viva if another will
    do. Pages not banked yet are banked now — a few at most."""
    turns = _turns(session, viva.id)
    asked_ids = [t.question_id for t in turns if t.kind == "question" and t.question_id]
    asked = set(asked_ids)
    plan = [tuple(ref) for ref in viva.plan]
    last = session.get(Question, asked_ids[-1]) if asked_ids else None
    start = (
        plan.index((last.material_id, last.page)) + 1
        if last and (last.material_id, last.page) in plan
        else 0
    )
    order = plan[start:] + plan[:start]
    before = _asked_before(session, viva.student, viva.id)
    item = len(asked_ids) + 1
    want = 1 if item <= 2 else 2 if item <= 4 else 3

    # Short and long in turn, the way an examiner works: a quick fact, then
    # "explain…", then a quick one again. The first is a short one.
    last_length = last.answer_length if last is not None else "long"

    def rank(q: Question, position: int = 0) -> tuple:
        return (
            q.id in before,
            q.answer_length == last_length,
            position,
            last is not None and q.family == last.family,
            abs(q.difficulty - want),
            q.span_start,
        )

    def ready(ref: tuple) -> list[Question]:
        return [q for q in bank.asked_from(session, [ref]) if q.id not in asked]

    # A lab viva walks the experiment the way a lab examiner does (FR-20.19):
    # principle, procedure, observations, result, precautions, sources of
    # error — a step the manual does not state is skipped, and the walk goes
    # round again when there are more questions than steps. The aim was the
    # warm-up, so a question on it comes only when nothing else is left.
    # Within a step, the usual choice: new to this student, short and long
    # in turn.
    lab = style_of(viva) == "lab"
    steps: dict[int, int] = {}
    for question_id in asked_ids if lab else ():
        done = session.get(Question, question_id)
        if done is not None:
            steps[lab_stage(done)] = steps.get(lab_stage(done), 0) + 1

    def walk() -> Question | None:
        pool = [
            (position, q)
            for position, ref in enumerate(plan)
            if bank.current(session.get(bank.BankPage, ref))
            for q in ready(ref)
        ]
        if not pool:
            return None

        def step(pq: tuple[int, Question]) -> tuple:
            stage = lab_stage(pq[1])
            return (pq[1].family == "aim", steps.get(stage, 0), stage, *rank(pq[1], pq[0]))

        return min(pool, key=step)[1]

    if lab and (chosen := walk()) is not None:
        return chosen

    # First what is banked already, in the order the viva walks the scope:
    # the background bank works ahead of the student, so this is usually
    # where the next question is, and nobody waits on a model for it. The
    # next two pages with questions are weighed together, so a page with only
    # short questions does not make two short ones in a row — the length
    # alternates, and the walk moves on at most one page further for it.
    window: list[tuple[int, Question]] = []
    for ref in order:
        if bank.current(session.get(bank.BankPage, ref)) and ready(ref):
            position = len({p for p, _ in window})
            window += [(position, q) for q in ready(ref)]
            if position + 1 >= LENGTH_WINDOW:
                break
    if window:
        return min(window, key=lambda pq: rank(pq[1], pq[0]))[1]
    # Then bank on demand — after committing, so no write is held while the
    # model is asked (SQLite has one writer).
    session.commit()
    banked_now = 0
    for ref in order:
        if bank.current(session.get(bank.BankPage, ref)) or banked_now >= BANK_ON_DEMAND:
            continue
        bank.ensure(session, ref[0], ref[1], llm=llm)
        banked_now += 1
        if ready(ref):
            # A page is banked with its whole part, so a lab walk now sees
            # every step of those pages.
            return walk() if lab else min(ready(ref), key=rank)
    return None


def prefetch(session: Session, viva_id: str, *, llm: Any = None, ahead: int = PREFETCH) -> int:
    """Bank the next pages of a viva's plan while the student answers."""
    viva = session.get(Viva, viva_id)
    if viva is None or viva.status != "live":
        return 0
    turns = _turns(session, viva.id)
    asked_ids = [t.question_id for t in turns if t.kind == "question" and t.question_id]
    plan = [tuple(ref) for ref in viva.plan]
    last = session.get(Question, asked_ids[-1]) if asked_ids else None
    start = (
        plan.index((last.material_id, last.page))
        if last and (last.material_id, last.page) in plan
        else 0
    )
    done = 0
    for ref in plan[start:] + plan[:start]:
        if done >= ahead:
            break
        if not bank.current(session.get(bank.BankPage, ref)):
            bank.ensure(session, ref[0], ref[1], llm=llm)
            done += 1
    if done == 0:
        # This part is ready: the next one is prepared while the student
        # answers, so "pages 11–20" is ready when they finish these.
        after = next_part(session, viva)
        if after is not None and not after["ready"]:
            bank.ensure(session, after["material_id"], after["first"], llm=llm)
            done += 1
    return done


# ── Parts: a long document, ten pages at a time ─────────────────────────────


def _text_pages(session: Session, material_id: str, first: int, last: int) -> list[int]:
    rows = session.exec(
        select(MaterialPage.page, func.length(MaterialPage.text)).where(
            MaterialPage.material_id == material_id,
            MaterialPage.page >= first,
            MaterialPage.page <= last,
        )
    ).all()
    return sorted(page for page, length in rows if (length or 0) >= bank.MIN_PAGE_CHARS)


def _part_ready(session: Session, material_id: str, pages: list[int]) -> bool:
    return all(bank.current(session.get(bank.BankPage, (material_id, p))) for p in pages)


def parts(session: Session, material: Material, student: str | None) -> list[dict[str, Any]]:
    """A document's parts: which pages each holds, which of them are only a
    picture (no text to ask from, said rather than hidden), how many
    questions are ready, and whether this student has done a viva on it."""
    done: set[tuple[int, int]] = set()
    if student:
        for viva in session.exec(
            select(Viva).where(Viva.student == student, Viva.status == "ended")
        ).all():
            span = (viva.scope.get("pages") or {}).get(material.id)
            if span and viva.end_reason == "complete":
                done.add((span[0], span[1]))
    out = []
    for first in range(1, max(material.pages, 1) + 1, bank.PART_PAGES):
        last = min(first + bank.PART_PAGES - 1, material.pages)
        text = _text_pages(session, material.id, first, last)
        questions = session.exec(
            select(func.count())
            .select_from(Question)
            .where(
                Question.material_id == material.id,
                Question.page >= first,
                Question.page <= last,
                Question.status.in_(("draft", "reviewed")),
                Question.prompt_version == bank.PROMPT_VERSION,
            )
        ).one()
        out.append(
            {
                "part": len(out) + 1,
                "first": first,
                "last": last,
                "pages_with_text": len(text),
                "picture_pages": [p for p in range(first, last + 1) if p not in text],
                "questions": questions,
                "ready": bool(text) and _part_ready(session, material.id, text),
                "done": (first, last) in done,
            }
        )
    return out


def span_of(session: Session, viva: Viva) -> dict[str, Any] | None:
    """The pages of one document a viva is on, when it is on a part."""
    spans = viva.scope.get("pages") or {}
    if len(spans) != 1:
        return None
    material_id, (first, last) = next(iter(spans.items()))
    material = session.get(Material, material_id)
    if material is None:
        return None
    return {"material_id": material_id, "first": first, "last": min(last, material.pages)}


def next_part(session: Session, viva: Viva) -> dict[str, Any] | None:
    """For a viva on one part of a document, the next part with something to
    ask — ten pages of pictures are passed over, not offered."""
    span = span_of(session, viva)
    if span is None:
        return None
    material = session.get(Material, span["material_id"])
    first = span["last"] + 1
    while first <= material.pages:
        end = min(first + bank.PART_PAGES - 1, material.pages)
        text = _text_pages(session, material.id, first, end)
        if text:
            return {
                "material_id": material.id,
                "title": material.title,
                "first": first,
                "last": end,
                "pages_with_text": len(text),
                "ready": _part_ready(session, material.id, text),
            }
        first = end + 1
    return None


# ── The examiner's lines ────────────────────────────────────────────────────

_CORRECT = ["Right.", "Yes, that's right.", "Good.", "Correct."]
_CORRECT_AFTER = ["Yes — that's it.", "That's it.", "Right, that's the point."]
_CONNECT = ["Next: ", "Now, ", "Moving on. ", "Alright. "]
_PARTIAL = ["That's part of it. ", "Partly. ", "Okay — and ", "Some of it. "]
_WRONG = ["Not quite. ", "That's not right. ", "No, not quite. "]
_BLANK = ["Take a moment. ", "That's alright. ", "Think about it for a second. "]


def _connect(lead: str, question: str) -> str:
    """ "Now, " runs into the question, so its capital goes ("Now, why…") —
    unless the word is a name or an acronym ("Now, LRU…", "Now, Belady's…")."""
    if lead.endswith(", ") and question[:1].isupper():
        first = question.split(" ", 1)[0]
        if not (first[1:2].isupper() or "'" in first or "’" in first):
            question = question[0].lower() + question[1:]
    return lead + question


def _join_points(points: list[str]) -> str:
    cleaned = [p.rstrip(". ") for p in points if p]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0] + "."
    return "; ".join(cleaned[:-1]) + "; and " + cleaned[-1] + "."


def _teach(session: Session, question: Question, missing: list[str], whole: bool) -> str:
    material = session.get(Material, question.material_id)
    title = material.title if material else "the material"
    lead = "Let me tell you, then: " if whole else "The rest of it: "
    return (
        f"{lead}{_join_points(missing)} "
        f"It's on page {question.page} of {title} — worth reading again."
    )


def _hint(question: Question) -> str:
    return question.hint or "Start from what it is for, and work out from there."


# ── The flow ────────────────────────────────────────────────────────────────

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def lock(viva_id: str) -> threading.Lock:
    """One answer at a time per viva: a double-submitted answer must not be
    marked twice or open two questions."""
    with _locks_guard:
        return _locks.setdefault(viva_id, threading.Lock())


def start(
    session: Session,
    viewer: Viewer,
    course_id: str,
    *,
    material_ids: list[str] | None = None,
    unit: str | None = None,
    pages: dict[str, list[int]] | None = None,
    mode: str = "typed",
    questions: int = DEFAULT_QUESTIONS,
    style: str = "course",
) -> Viva:
    if viewer.subject is None:
        raise VivaError(401, "Sign in to take a viva.")
    if mode not in ("typed", "spoken"):
        raise VivaError(422, "A viva is typed or spoken.")
    if style not in ("course", "lab"):
        raise VivaError(422, "A viva is on a course or a lab.")
    live = session.exec(
        select(Viva).where(Viva.student == viewer.subject, Viva.status == "live")
    ).all()
    for old in live:
        # One viva at a time: starting another ends the one left open.
        end(session, old, reason="replaced")
    scope = resolve_scope(
        session, viewer, course_id, material_ids=material_ids, unit=unit, pages=pages
    )
    if not scope.pages:
        why = (
            " " + "; ".join(f"{e['title']}: {e['why']}" for e in scope.excluded) + "."
            if scope.excluded
            else ""
        )
        raise VivaError(
            422,
            "There is nothing here to be examined on yet — add notes, slides or a lab manual "
            f"with text to this course.{why}",
        )
    target = min(MAX_QUESTIONS, max(MIN_QUESTIONS, int(questions or DEFAULT_QUESTIONS)))
    viva = Viva(student=viewer.subject, course_id=course_id, mode=mode, target=target)
    viva.examiner = random.Random(viva.id).choice(EXAMINERS)["id"]
    viva.scope = {
        "label": scope.label,
        "material_ids": [m.id for m in scope.materials],
        "unit": unit,
        "pages": pages or {},
        "excluded": scope.excluded,
        "style": style,
    }
    viva.plan = _visit_order(scope.pages, target, viva.id)
    session.add(viva)
    session.flush()

    name = _examiner(viva)["name"]
    kind = "lab viva" if style == "lab" else "viva"
    span = span_of(session, viva)
    on = f"{scope.label}, pages {span['first']} to {span['last']}" if span else scope.label
    _say(
        session,
        viva,
        "examiner",
        "greeting",
        # Said aloud: short, the way an examiner opens. The course is on screen.
        f"Hello, I'm {name}. This is your {kind} on {on} — {target} questions. "
        "If you don't know something, just say so.",
        0,
    )
    # An experiment opens on its aim; anything else on what it is about.
    lab = style == "lab" or all(m.kind == "lab_manual" for m in scope.materials)
    warmup = (
        f"Let's begin with an easy one. In your own words, what is the aim of {scope.label}?"
        if lab
        else f"Let's begin with an easy one. In your own words, what is {scope.label} about?"
    )
    _say(session, viva, "examiner", "warmup", warmup, 0)
    viva.open = {"item": 0, "kind": "warmup", "stage": "asked", "covered": [], "probed": []}
    session.add(viva)
    session.commit()
    session.refresh(viva)
    return viva


def _ask_next(session: Session, viva: Viva, *, llm: Any = None) -> None:
    done = sum(1 for t in _turns(session, viva.id) if t.kind == "question")
    if done >= viva.target:
        _close(session, viva, "complete")
        return
    question = _next_question(session, viva, llm=llm)
    if question is None:
        _say(
            session,
            viva,
            "examiner",
            "close",
            "That's everything the material in scope gave me to ask. Your report has what we "
            "covered, and what to read again.",
            done,
        )
        _finish(viva, "complete")
        return
    item = done + 1
    text = question.text if item == 1 else _connect(_pick(viva, _CONNECT, item), question.text)
    _say(session, viva, "examiner", "question", text, item, question_id=question.id)
    viva.open = {
        "item": item,
        "kind": "question",
        "question_id": question.id,
        "stage": "asked",
        "covered": [],
        "probed": [],
    }


def _close(session: Session, viva: Viva, reason: str) -> None:
    lines = {
        "complete": "That's all from me. Thank you — your report shows what you knew, and "
        "what to read again.",
        "ended_by_student": "Alright, we'll stop here. Your report has what we covered.",
        "replaced": "We'll stop this one here.",
    }
    done = sum(1 for t in _turns(session, viva.id) if t.kind == "question")
    line = lines.get(reason, lines["complete"])
    after = next_part(session, viva) if reason == "complete" else None
    if after is not None:
        # A part of a longer document: say what comes next, as an examiner
        # taking a long subject in sittings would.
        line += f" When you're ready, we'll go on to pages {after['first']} to {after['last']}."
    _say(session, viva, "examiner", "close", line, done)
    _finish(viva, reason)


def _finish(viva: Viva, reason: str) -> None:
    viva.status = "ended"
    viva.end_reason = reason
    viva.ended_at = datetime.now(UTC)
    viva.open = None


def _clean_timing(timing: dict | None) -> dict | None:
    if not isinstance(timing, dict):
        return None
    out: dict[str, Any] = {}
    for key in ("silence_ms", "duration_ms"):
        value = timing.get(key)
        if isinstance(value, (int, float)) and 0 <= value <= 30 * 60 * 1000:
            out[key] = int(value)
    out["spoken"] = bool(timing.get("spoken"))
    return out


def answer(
    session: Session, viva: Viva, text: str, timing: dict | None = None, *, llm: Any = None
) -> Viva:
    if viva.status != "live" or viva.open is None:
        raise VivaError(409, "This viva is not waiting for an answer.")
    text = " ".join((text or "").split())[:4000]
    state = dict(viva.open)
    item = state["item"]
    # Marked BEFORE anything is written. SQLite has one writer: a request that
    # wrote its turn and then waited on the model held the write lock for the
    # whole call, and the bank filling the next pages in the background waited
    # 30 s and failed with "database is locked" (live, 2026-10-28).
    question = session.get(Question, state["question_id"]) if state["kind"] == "question" else None
    marked = (
        marking.mark(question, text, already=state.get("covered"), llm=llm) if question else None
    )
    turn = _say(
        session,
        viva,
        "student",
        "answer",
        text,
        item,
        question_id=state.get("question_id"),
        timing=_clean_timing(timing),
    )

    if state["kind"] == "warmup" or question is None or marked is None:
        _say(
            session,
            viva,
            "examiner",
            "ack",
            _pick(viva, ["Alright.", "Okay, thank you.", "Good."], 0),
            0,
        )
        _ask_next(session, viva, llm=llm)
        return _save(session, viva)

    turn.verdict = {**marked.as_verdict(question), "stage": state["stage"]}
    session.add(turn)
    points = [p["point"] for p in question.answer_points]
    missing = [i for i in range(len(points)) if i not in marked.covered]

    if marked.status == "correct":
        lines = _CORRECT if state["stage"] == "asked" else _CORRECT_AFTER
        _say(
            session,
            viva,
            "examiner",
            "ack",
            _pick(viva, lines, turn.seq),
            item,
            question_id=question.id,
        )
        viva.open = None
        _ask_next(session, viva, llm=llm)
    elif state["stage"] == "asked" and marked.status == "partial" and missing:
        probe = question.answer_points[missing[0]]["probe"]
        lead = _pick(viva, _PARTIAL, turn.seq)
        line = lead + (probe[0].lower() + probe[1:] if lead.endswith("and ") else probe)
        _say(session, viva, "examiner", "follow_up", line, item, question_id=question.id)
        viva.open = {
            **state,
            "stage": "follow_up",
            "covered": marked.covered,
            "probed": [missing[0]],
        }
    elif state["stage"] == "asked":
        lead = _pick(viva, _BLANK if marked.status == "blank" else _WRONG, turn.seq)
        line = f"{lead}Here's a hint: {_hint(question)}"
        _say(session, viva, "examiner", "hint", line, item, question_id=question.id)
        viva.open = {**state, "stage": "hint", "covered": marked.covered}
    else:
        whole = not marked.covered
        _say(
            session,
            viva,
            "examiner",
            "teach",
            _teach(session, question, [points[i] for i in missing], whole),
            item,
            question_id=question.id,
        )
        viva.open = None
        _ask_next(session, viva, llm=llm)
    return _save(session, viva)


def hint(session: Session, viva: Viva) -> Viva:
    """The student asks for a hint (once per question)."""
    state = viva.open
    if viva.status != "live" or state is None or state["kind"] != "question":
        raise VivaError(409, "There is no question to give a hint on.")
    if state["stage"] == "hint":
        raise VivaError(409, "You have had the hint for this one.")
    question = session.get(Question, state["question_id"])
    _say(
        session,
        viva,
        "examiner",
        "hint",
        f"Here's a hint: {_hint(question)}",
        state["item"],
        question_id=question.id,
    )
    viva.open = {**state, "stage": "hint"}
    return _save(session, viva)


def end(session: Session, viva: Viva, reason: str = "ended_by_student") -> Viva:
    if viva.status == "ended":
        return viva
    _close(session, viva, reason)
    return _save(session, viva)


def _save(session: Session, viva: Viva) -> Viva:
    session.add(viva)
    session.commit()
    session.refresh(viva)
    return viva


# ── What the room is shown ──────────────────────────────────────────────────


def state(session: Session, viva: Viva) -> dict[str, Any]:
    turns = _turns(session, viva.id)
    open_item = viva.open["item"] if viva.open else None
    course = session.get(Course, viva.course_id)
    out_turns = []
    for t in turns:
        closed = viva.status == "ended" or t.item != open_item
        row: dict[str, Any] = {
            "seq": t.seq,
            "role": t.role,
            "kind": t.kind,
            "text": t.text,
            "item": t.item,
        }
        if t.question_id and closed and t.kind in ("question", "teach"):
            question = session.get(Question, t.question_id)
            if question is not None:
                row["cite"] = _cite(session, question)
        if t.verdict and closed:
            row["verdict"] = t.verdict["status"]
        out_turns.append(row)
    asked = sum(1 for t in turns if t.kind == "question")
    open_question = (
        session.get(Question, viva.open["question_id"])
        if viva.open and viva.open.get("question_id")
        else None
    )
    return {
        "id": viva.id,
        "status": viva.status,
        "end_reason": viva.end_reason,
        "mode": viva.mode,
        "style": style_of(viva),
        "course": {"id": course.id, "code": course.code, "title": course.title} if course else None,
        "scope": {"label": viva.scope.get("label"), "excluded": viva.scope.get("excluded", [])},
        "part": span_of(session, viva),
        "examiner": _examiner(viva),
        "target": viva.target,
        "asked": asked,
        "turns": out_turns,
        "open": (
            {
                "item": viva.open["item"],
                "kind": viva.open["kind"],
                "stage": viva.open["stage"],
                "hint_available": viva.open["kind"] == "question" and viva.open["stage"] != "hint",
                # A line, or a few sentences — the room says which.
                "answer_length": open_question.answer_length if open_question else None,
            }
            if viva.open
            else None
        ),
        "started_at": viva.started_at.isoformat(),
        "ended_at": viva.ended_at.isoformat() if viva.ended_at else None,
        # A part of a longer document: the one after it, and whether its
        # questions are ready (they are banked while this one runs).
        "next_part": next_part(session, viva) if viva.status == "ended" else None,
    }


# ── The report (FR-20.18) ───────────────────────────────────────────────────


def _item_status(answers: list[VivaTurn]) -> tuple[str, list[str]]:
    """The question's outcome, and the help it took."""
    verdicts = [a.verdict for a in answers if a.verdict]
    if not verdicts:
        return "not_answered", []
    final = verdicts[-1]["status"]
    if final == "blank":
        # Tried, then gave up: what they tried is what they showed. "Didn't
        # know" would hide the attempt (live, 2026-10-28: "it's something
        # about the oldest page…", then "I don't know", read as blank).
        tried = [v["status"] for v in verdicts if v["status"] != "blank"]
        final = tried[-1] if tried else "blank"
    # The stage an answer was given at: a hint asked for before the first
    # answer counts as much as one given after it.
    help_taken = [v["stage"] for v in verdicts if v.get("stage") in ("follow_up", "hint")]
    help_taken = list(dict.fromkeys(help_taken))
    if final != "correct" and len(verdicts) >= 2:
        help_taken.append("taught")
    return final, help_taken


def report(session: Session, viva: Viva) -> dict[str, Any]:
    turns = _turns(session, viva.id)
    course = session.get(Course, viva.course_id)
    lab = style_of(viva) == "lab"
    items: list[dict[str, Any]] = []
    asked = [t for t in turns if t.kind == "question"]
    for q_turn in asked:
        question = session.get(Question, q_turn.question_id)
        answers = [t for t in turns if t.role == "student" and t.item == q_turn.item]
        examiner = [t for t in turns if t.role == "examiner" and t.item == q_turn.item]
        status, help_taken = _item_status(answers)
        if (
            status != "correct"
            and status != "not_answered"
            and not any(t.kind == "teach" for t in examiner)
        ):
            # Ended before the second try: told nothing, and the report says so.
            help_taken = [h for h in help_taken if h != "taught"]
        last = next((a.verdict for a in reversed(answers) if a.verdict), None)
        items.append(
            {
                "item": q_turn.item,
                "question": question.text if question else q_turn.text,
                "family": question.family if question else None,
                # A lab viva's step: "principle", "procedure", … (FR-20.19).
                "stage": stage_name(question) if question and lab else None,
                "answer_length": question.answer_length if question else None,
                "difficulty": question.difficulty if question else None,
                "status": status,
                "help": help_taken,
                "answers": [
                    {
                        "text": a.text,
                        "status": (a.verdict or {}).get("status"),
                        "measures": speaking.measure(a.text, a.timing),
                    }
                    for a in answers
                ],
                "covered": (last or {}).get("covered", []),
                "missing": (last or {}).get(
                    "missing", [p["point"] for p in question.answer_points] if question else []
                ),
                "wrong": next(
                    (a.verdict["wrong"] for a in answers if a.verdict and a.verdict.get("wrong")),
                    None,
                ),
                "marked_by": (last or {}).get("marked_by"),
                "cite": _cite(session, question) if question else None,
                "written_by": question.generated_by if question else None,
                "reviewed": bool(question and question.status == "reviewed"),
                "exchange": [
                    {"role": t.role, "kind": t.kind, "text": t.text}
                    for t in turns
                    if t.item == q_turn.item
                ],
            }
        )

    counts = {
        k: sum(1 for i in items if i["status"] == k)
        for k in ("correct", "partial", "missed", "incorrect", "blank", "not_answered")
    }
    knew = [i["item"] for i in items if i["status"] == "correct" and not i["help"]]
    reread: dict[tuple[str, int], dict[str, Any]] = {}
    for i in items:
        if (i["status"] == "correct" and not i["help"]) or not i["cite"]:
            continue
        cite = i["cite"]
        key = (cite["material_id"], cite["page"])
        entry = reread.setdefault(
            key,
            {
                "material_id": cite["material_id"],
                "title": cite["title"],
                "page": cite["page"],
                "quotes": [],
                "items": [],
            },
        )
        if cite["quote"] not in entry["quotes"]:
            entry["quotes"].append(cite["quote"])
        entry["items"].append(i["item"])

    student_answers = [t for t in turns if t.role == "student"]
    sounded = speaking.summary([speaking.measure(t.text, t.timing) for t in student_answers])

    history = session.exec(
        select(Viva)
        .where(Viva.student == viva.student, Viva.status == "ended")
        .order_by(Viva.started_at)
    ).all()
    summaries = []
    for past in history:
        past_answers = session.exec(
            select(VivaTurn).where(VivaTurn.viva_id == past.id, VivaTurn.role == "student")
        ).all()
        if past_answers:
            summaries.append(
                speaking.summary([speaking.measure(t.text, t.timing) for t in past_answers])
            )

    return {
        "viva": {
            "id": viva.id,
            "course": {"id": course.id, "code": course.code, "title": course.title}
            if course
            else None,
            "scope": viva.scope.get("label"),
            "part": span_of(session, viva),
            "examiner": _examiner(viva)["name"],
            "mode": viva.mode,
            "style": style_of(viva),
            "status": viva.status,
            "end_reason": viva.end_reason,
            "target": viva.target,
            "started_at": viva.started_at.isoformat(),
            "ended_at": viva.ended_at.isoformat() if viva.ended_at else None,
        },
        "coverage": _coverage(session, viva, items),
        "next_part": next_part(session, viva),
        "counts": counts,
        "items": items,
        "knew": knew,
        "reread": list(reread.values()),
        "sounded": sounded,
        "trend": speaking.trend(summaries),
        # An answer matched by its words because no model answered — not an
        # "I don't know", which is always recognised by rule (live: the note
        # said the model was down when it was not).
        "marked_by_rules": any(
            t.verdict.get("marked_by") == marking.RULES and t.verdict.get("status") != "blank"
            for t in student_answers
            if t.verdict
        ),
    }


def _coverage(session: Session, viva: Viva, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """For a viva on a part of one document: the pages the questions came
    from, and the pages no question could come from (pictures) — so a student
    knows what this sitting covered and what it could not."""
    spans = viva.scope.get("pages") or {}
    if len(spans) != 1:
        return None
    material_id, (first, last) = next(iter(spans.items()))
    material = session.get(Material, material_id)
    if material is None:
        return None
    last = min(last, material.pages)
    text = _text_pages(session, material_id, first, last)
    asked = sorted({i["cite"]["page"] for i in items if i.get("cite")})
    return {
        "material_id": material_id,
        "title": material.title,
        "first": first,
        "last": last,
        "asked_from": asked,
        "picture_pages": [p for p in range(first, last + 1) if p not in text],
    }


def history(session: Session, student: str, limit: int = 30) -> list[dict[str, Any]]:
    rows = session.exec(
        select(Viva).where(Viva.student == student).order_by(Viva.started_at.desc()).limit(limit)
    ).all()
    out = []
    for viva in rows:
        course = session.get(Course, viva.course_id)
        answers = session.exec(
            select(VivaTurn).where(
                VivaTurn.viva_id == viva.id, VivaTurn.role == "student", VivaTurn.item > 0
            )
        ).all()
        by_item: dict[int, list[VivaTurn]] = {}
        for a in answers:
            by_item.setdefault(a.item, []).append(a)
        # The report's rule, so the list and the report never disagree.
        finals = {
            item: status
            for item, turns in by_item.items()
            if (status := _item_status(turns)[0]) != "not_answered"
        }
        out.append(
            {
                "id": viva.id,
                "course": {"id": course.id, "code": course.code, "title": course.title}
                if course
                else None,
                "scope": viva.scope.get("label"),
                "part": span_of(session, viva),
                "status": viva.status,
                "mode": viva.mode,
                "style": style_of(viva),
                "started_at": viva.started_at.isoformat(),
                "target": viva.target,
                "correct": sum(1 for s in finals.values() if s == "correct"),
                "answered": len(finals),
            }
        )
    return out
