"""The folder tree students and faculty already think in, made literal
(FR-20.6, FR-20.7):

    Amrita University/<Campus>/<Branch>/Semester_<n>/<CODE - Title>/<files>
    Amrita University/<Campus>/<Branch>/Electives/<Basket>/<CODE - Title>/<files>

`scaffold` creates every folder from the catalogue, so a contributor only drops
files in. `plan` reads a tree (on disk, or the paths of a browser folder upload)
and says where every file would go, and why any would not — nothing is dropped
silently. `run` adds them; a re-run adds nothing (EC-20.4, AC-20.5).

Inside a course folder, a sub-folder or the file name says what it is: `lab`,
`slides`, `qp`/`pyq`/`question paper`, `syllabus`, `reference`, else notes;
`unit 3` / `lab 6` / `experiment 6` says which part.
"""

from __future__ import annotations

import io
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from sqlmodel import Session, select

from .library import latest_parsed
from .materials import MaterialError, add_file
from .models import Campus, Course, Institution, Offering, Programme

ROOT_FOLDER = "Amrita University"
CODE = re.compile(r"\b(\d{2}[A-Z]{3}\d{3})\b")
SEMESTER = re.compile(r"^semester[ _-]*(\d{1,2})$", re.I)
UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
#: Windows still trips over long paths; a course folder name is kept short.
MAX_NAME = 70
SKIP_FILES = {"readme.txt", "desktop.ini", "thumbs.db", ".ds_store"}

KIND_HINTS = (
    ("lab_manual", re.compile(r"\blab|practical|experiment|\bexp\b", re.I)),
    ("slides", re.compile(r"slide|\bppt|lecture deck", re.I)),
    (
        "question_paper",
        re.compile(r"\bqp\b|pyq|question[ _-]*paper|previous[ _-]*year|(end|mid)[ _-]*sem", re.I),
    ),
    ("syllabus", re.compile(r"syllab", re.I)),
    ("reference", re.compile(r"reference|text[ _-]*book|\bbook", re.I)),
)  # fmt: skip
UNIT = re.compile(r"\bunit[ _-]*(\d{1,2})\b", re.I)
LAB = re.compile(r"\b(?:lab|experiment|exp|expt)[ _-]*(\d{1,2})\b", re.I)


def safe(name: str) -> str:
    name = UNSAFE.sub("-", name).strip().rstrip(".")
    return name[:MAX_NAME].rstrip(" .-") or "untitled"


def branch_label(prog: Programme, siblings: list[Programme]) -> str:
    """ "CSE", or "CSE - Cyber Security" where two branches share a code."""
    same = [p for p in siblings if p.short == prog.short]
    if len(same) <= 1:
        return safe(prog.short)
    inner = re.search(r"\(([^)]*)\)\s*$", prog.name)
    return safe(f"{prog.short} - {inner.group(1) if inner else prog.name}")


def course_label(course: Course) -> str:
    return safe(f"{course.code} - {course.title}")


def guess_kind(parts: list[str]) -> str:
    joined = " ".join(parts)
    return next((kind for kind, pattern in KIND_HINTS if pattern.search(joined)), "notes")


def guess_unit(parts: list[str]) -> str | None:
    joined = " ".join(parts)
    if m := LAB.search(joined):
        return f"Lab {int(m.group(1))}"
    if m := UNIT.search(joined):
        return f"Unit {int(m.group(1))}"
    return None


# ── scaffold ──────────────────────────────────────────────────────────────


def scaffold(session: Session, target: Path) -> dict[str, int]:
    """Create the whole tree under `target`. Existing folders are left alone."""
    inst = session.exec(select(Institution)).first()
    root = target / safe(inst.display if inst else ROOT_FOLDER)
    counts = {"campuses": 0, "branches": 0, "courses": 0}
    for camp in session.exec(select(Campus).order_by(Campus.position)).all():
        progs = _offered(session, camp.id)
        counts["campuses"] += 1
        for prog in progs:
            cur = latest_parsed(session, prog.id)
            base = root / safe(camp.name) / branch_label(prog, progs)
            base.mkdir(parents=True, exist_ok=True)
            counts["branches"] += 1
            if cur is None:
                continue
            for course in session.exec(select(Course).where(Course.curriculum_id == cur.id)).all():
                if course.semester is not None:
                    folder = base / f"Semester_{course.semester}" / course_label(course)
                else:
                    folder = (
                        base
                        / "Electives"
                        / safe(course.basket or "Electives")
                        / course_label(course)
                    )
                folder.mkdir(parents=True, exist_ok=True)
                counts["courses"] += 1
    (root / "README.txt").write_text(README, encoding="utf-8")
    return counts


def scaffold_zip(session: Session) -> bytes:
    """The same empty tree, as a zip a curator downloads, fills and uploads back."""
    with tempfile.TemporaryDirectory() as tmp:
        scaffold(session, Path(tmp))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(Path(tmp).rglob("*")):
                name = path.relative_to(tmp).as_posix()
                if path.is_dir():
                    archive.writestr(name + "/", "")  # the empty folders are the point
                else:
                    archive.write(path, name)
        return out.getvalue()


README = """\
Put each file in its course's folder:

  <Campus>/<Branch>/Semester_<n>/<CODE - Course title>/

Sub-folders or file names say what a file is and which part of the course:
  lab / experiment  ->  lab manual        slides / ppt  ->  slides
  qp / pyq / question paper  ->  question paper
  syllabus  ->  syllabus      reference / textbook  ->  reference
  anything else  ->  notes
  unit 3 / lab 6 / experiment 6 in a name  ->  which unit or lab

A course's material is shared with every campus that runs the course; the
campus folder you used is remembered as where it came from.

Then import it (dry run first):
  python -m backend_M20_Course_Viva.jobs.import_tree "<this folder>" --dry-run
  python -m backend_M20_Course_Viva.jobs.import_tree "<this folder>"
"""


# ── plan and run ──────────────────────────────────────────────────────────


@dataclass
class Placement:
    path: str
    course_id: str
    campus_id: str
    kind: str
    unit: str | None


@dataclass
class Plan:
    placed: list[Placement] = field(default_factory=list)
    problems: list[dict] = field(default_factory=list)  # {"path", "reason"}


def _offered(session: Session, campus_id: str) -> list[Programme]:
    return list(
        session.exec(
            select(Programme)
            .join(Offering, Offering.programme_id == Programme.id)
            .where(Offering.campus_id == campus_id)
            .order_by(Programme.name)
        ).all()
    )


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def locate(session: Session, relative: str) -> tuple[Placement | None, str | None]:
    """Where one file goes, or why it cannot."""
    parts = [p for p in PurePosixPath(relative.replace("\\", "/")).parts if p not in ("", ".")]
    campuses = {_norm(c.name): c for c in session.exec(select(Campus)).all()}
    start = next((i for i, p in enumerate(parts) if _norm(p) in campuses), None)
    if start is None:
        return None, "no campus folder (Amritapuri, Coimbatore, …) in its path"
    camp = campuses[_norm(parts[start])]
    rest = parts[start + 1 :]
    if len(rest) < 3:
        return None, "expected <Branch>/Semester_<n>/<Course>/ under the campus"
    progs = _offered(session, camp.id)
    branch = _norm(rest[0])
    prog = next(
        (
            p
            for p in progs
            if branch in {_norm(branch_label(p, progs)), _norm(p.short), _norm(p.name)}
        ),
        None,
    )
    if prog is None:
        return None, f"{camp.name} does not run a branch called {rest[0]!r}"
    cur = latest_parsed(session, prog.id)
    if cur is None:
        return None, f"{prog.name} has no course list yet"
    sem_match = SEMESTER.match(rest[1].strip())
    course_parts = rest[2:]
    if not sem_match and _norm(rest[1]) == "electives":
        course_parts = rest[3:] if len(rest) > 3 else []
    elif not sem_match:
        return None, f"expected Semester_<n> or Electives, found {rest[1]!r}"
    if len(course_parts) < 2:
        return None, "the file must be inside a course folder"
    folder, inner = course_parts[0], course_parts[1:]
    course = None
    if code := CODE.search(folder):
        course = session.get(Course, f"{cur.id}:{code.group(1)}")
    if course is None and sem_match:
        title = _norm(folder)
        course = session.exec(
            select(Course).where(
                Course.curriculum_id == cur.id, Course.semester == int(sem_match.group(1))
            )
        ).all()
        course = next((c for c in course if _norm(c.title) == title), None)
    if course is None:
        return None, f"no course {folder!r} in {prog.short} {cur.year}"
    return (
        Placement(
            path=relative,
            course_id=course.id,
            campus_id=camp.id,
            kind=guess_kind(inner),
            unit=guess_unit(inner),
        ),
        None,
    )


def plan(session: Session, relatives: list[str]) -> Plan:
    result = Plan()
    for relative in relatives:
        name = PurePosixPath(relative.replace("\\", "/")).name
        if name.casefold() in SKIP_FILES or name.startswith("~$"):
            continue
        placement, reason = locate(session, relative)
        if placement:
            result.placed.append(placement)
        else:
            result.problems.append({"path": relative, "reason": reason})
    return result


def run(
    session: Session,
    files: dict[str, bytes],
    added_by: str,
    *,
    shared: bool = False,
    visibility: str = "platform",
) -> dict:
    """Add every placeable file. `files`: relative path -> bytes."""
    result = plan(session, list(files))
    added, existing, failed = 0, 0, list(result.problems)
    for placement in result.placed:
        try:
            outcome = add_file(
                session,
                course_id=placement.course_id,
                data=files[placement.path],
                filename=PurePosixPath(placement.path.replace("\\", "/")).name,
                added_by=added_by,
                kind=placement.kind,
                unit=placement.unit,
                campus_id=None if shared else placement.campus_id,
                visibility=visibility,
                permission="added by folder import",
                by_curator=True,
            )
        except MaterialError as exc:
            failed.append({"path": placement.path, "reason": str(exc)})
            continue
        if outcome.created:
            added += 1
        else:
            existing += 1
    return {"added": added, "already_there": existing, "problems": failed}
