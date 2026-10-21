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
    __table_args__ = (UniqueConstraint("course_id", "sha256", name="uq_material_course_hash"),)

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
