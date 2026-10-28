"""The library's tables (spec §5).

Institution → Campus → (Offering) → Programme → Curriculum → Course → Material.

Courses belong to a CURRICULUM, not a campus: Amrita's curricula are
university-wide per regulation year, so B.Tech CSE 2023 is one course list at
every campus that runs it, and its material is uploaded once (spec Trap 1). A
campus OFFERS a programme; a material may carry the campus it came from.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Meta(SQLModel, table=True):
    """Small facts about the database itself (which catalogue it holds)."""

    key: str = Field(primary_key=True)
    value: str


class Institution(SQLModel, table=True):
    id: str = Field(primary_key=True)  # "amrita"
    name: str
    display: str


class Campus(SQLModel, table=True):
    id: str = Field(primary_key=True)  # "coimbatore"
    institution_id: str = Field(foreign_key="institution.id", index=True)
    name: str
    position: int = 0


class Programme(SQLModel, table=True):
    id: str = Field(primary_key=True)  # "btech-cse-computer-science-and-engineering"
    institution_id: str = Field(foreign_key="institution.id", index=True)
    degree: str  # "B.Tech"
    name: str  # "Computer Science and Engineering"
    short: str  # "CSE", the department's own course-code prefix where known
    school: str  # "Engineering" | "Artificial Intelligence"
    source_url: str | None = None
    also_at: list = Field(default_factory=list, sa_column=Column(JSON))


class Offering(SQLModel, table=True):
    """Programme P is offered at campus C — from P's own page."""

    campus_id: str = Field(foreign_key="campus.id", primary_key=True)
    programme_id: str = Field(foreign_key="programme.id", primary_key=True)
    source_url: str | None = None


class Curriculum(SQLModel, table=True):
    id: str = Field(primary_key=True)  # "<programme>-2023"
    programme_id: str = Field(foreign_key="programme.id", index=True)
    year: int
    #: [{"label", "url"}] — the university's PDFs for this regulation year.
    documents: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "listed"  # listed | parsed | failed
    parsed_from: str | None = None
    warnings: list = Field(default_factory=list, sa_column=Column(JSON))
    #: Elective slots per semester: {"4": [{"kind", "title", "credits"}]}
    slots: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Course(SQLModel, table=True):
    id: str = Field(primary_key=True)  # "<curriculum>:<code>"
    curriculum_id: str = Field(foreign_key="curriculum.id", index=True)
    code: str = Field(index=True)
    title: str
    semester: int | None = Field(default=None, index=True)
    basket: str | None = None  # an elective basket's name, for electives
    category: str | None = None
    ltp: str | None = None
    credits: str | None = None
    syllabus: str | None = None  # the units, from the curriculum PDF
    syllabus_page: int | None = None  # where they start in that PDF


class Material(SQLModel, table=True):
    # One per course, file and uploader: a private copy is its owner's alone
    # (AC-20.3), so a second student's copy of the same file is a row of its
    # own. One file shared with everyone stays one material (`materials`).
    __table_args__ = (
        UniqueConstraint("course_id", "sha256", "added_by", name="uq_material_course_hash_owner"),
    )

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    course_id: str = Field(foreign_key="course.id", index=True)
    #: The campus it came from, if any. Informational: material is shared
    #: across campuses unless its visibility says otherwise (FR-20.10).
    campus_id: str | None = Field(default=None, foreign_key="campus.id")
    title: str
    kind: str  # syllabus | notes | slides | lab_manual | question_paper | reference | video | other
    unit: str | None = None  # "Unit 3", "Lab 6"
    filename: str | None = None
    url: str | None = None  # a link, instead of a file
    mime: str | None = None
    bytes: int = 0
    sha256: str | None = Field(default=None, index=True)
    pages: int = 0
    text_status: str = "pending"  # ok | no_text | failed | link
    visibility: str = "platform"  # private | held | platform
    permission: str | None = None  # what the uploader said about sharing it
    added_by: str
    status: str = "published"  # published | removed
    created_at: datetime = Field(default_factory=_now)


class MaterialPage(SQLModel, table=True):
    material_id: str = Field(foreign_key="material.id", primary_key=True)
    page: int = Field(primary_key=True)  # 1-based
    text: str


# ── Phase 2: the viva (spec §5, §6.4) ───────────────────────────────────────


class BankPage(SQLModel, table=True):
    """One page of material, banked: its questions are written once and kept
    (FR-20.14, Trap 8). `generated_by` is the model's id, or "rules" when the
    questions were written by rule because no model answered — those pages
    are tried again when one does."""

    material_id: str = Field(foreign_key="material.id", primary_key=True)
    page: int = Field(primary_key=True)
    status: str = "ready"  # ready | empty | failed
    generated_by: str = ""
    prompt_version: str = ""
    questions: int = 0
    attempts: int = 0
    reason: str | None = None
    updated_at: datetime = Field(default_factory=_now)


class Question(SQLModel, table=True):
    """A viva question, and the span of its page it is drawn from (Trap 4).

    `span_start`/`span_end` index the page's text and `quote` is that text: a
    question whose quote is not in its page is never stored (AC-20.2)."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    material_id: str = Field(foreign_key="material.id", index=True)
    page: int
    span_start: int
    span_end: int
    quote: str
    #: definition | explain | procedure | observation | application | numerical | compare
    family: str
    text: str
    #: [{"point": what a good answer says, "probe": a follow-up that asks for it
    #: without giving it away}]
    answer_points: list = Field(default_factory=list, sa_column=Column(JSON))
    #: A nudge toward the answer that does not state it.
    hint: str = ""
    difficulty: int = 1  # 1 recall · 2 understanding · 3 application
    #: short: one fact in a line (a term, a value, a name) · long: explained in
    #: a few sentences (why, how, the steps, a comparison). A viva asks both.
    answer_length: str = "long"
    status: str = "draft"  # draft | reviewed | retired
    generated_by: str = ""
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=_now)


class Viva(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    student: str = Field(index=True)
    course_id: str = Field(foreign_key="course.id", index=True)
    #: {"label", "material_ids", "unit", "pages": {material_id: [from, to]}}
    scope: dict = Field(default_factory=dict, sa_column=Column(JSON))
    #: The pages in scope, in the order the viva walks them: [[material_id, page]].
    plan: list = Field(default_factory=list, sa_column=Column(JSON))
    mode: str = "typed"  # typed | spoken
    examiner: str = ""
    target: int = 6  # how many questions, after the warm-up
    status: str = "live"  # live | ended
    end_reason: str | None = None  # complete | ended_by_student
    #: The item the student is answering, or None between items:
    #: {"item", "kind": warmup|question, "question_id", "stage": asked|follow_up|hint,
    #:  "covered": [point indexes reached so far], "probed": [point indexes asked about]}
    open: dict | None = Field(default=None, sa_column=Column(JSON))
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None


class VivaTurn(SQLModel, table=True):
    """One line of the viva, the examiner's or the student's."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    viva_id: str = Field(foreign_key="viva.id", index=True)
    seq: int
    role: str  # examiner | student
    #: examiner: greeting | warmup | question | follow_up | hint | teach | ack | close
    #: student: answer
    kind: str
    text: str
    item: int = 0  # which question this belongs to; 0 is the warm-up
    question_id: str | None = None
    #: A student answer's marking: {"status", "covered", "missing", "wrong", "marked_by"}
    verdict: dict | None = Field(default=None, sa_column=Column(JSON))
    #: What the client measured: {"silence_ms", "duration_ms", "spoken"}
    timing: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


KINDS = (
    "syllabus",
    "notes",
    "slides",
    "lab_manual",
    "question_paper",
    "reference",
    "video",
    "other",
)
#: What an uploader may ask for. `held` is the library's answer to "platform"
#: with no permission stated: seen by its uploader and curators until one
#: approves it (EC-20.8).
VISIBILITIES = ("private", "platform")
