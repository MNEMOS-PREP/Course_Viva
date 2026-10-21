"""Read an Amrita curriculum PDF: semesters, courses, elective baskets, and each
course's syllabus units with the page they are on.

Ported from M04's `jobs/curricula.py` (2026-10-13), which parses this layout
for B.Tech CSE 2023 and AIE 2022, without its ontology mapping (M04 keeps
that: it is about concepts; this module is about material). Changes:

* the category cell is any department tag (`ECE`, `MEE`, `CSE / ENGG`), not
  only CSE's, so every branch's tables read;
* each syllabus keeps the PDF page it starts on, so a viva question drawn from
  it can cite the page (spec Trap 4);
* the programme's name comes from the catalogue, not the PDF's cover.

Two techniques, each where it is strong: PyMuPDF's table cells for the
semester tables, and the syllabus pages' own "<code> <TITLE> L-T-P-C" headings
as a second source, so a disagreement is reported, never silently resolved.

Needs PyMuPDF (`pip install -e ".[sync]"`): a build step run when the
university publishes a curriculum, never a request path.

To do (TODO §1 risks): move this reader into Platform_Core so M04 and M20
share one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CODE = re.compile(r"^(\d{2}[A-Z]{3}\d{3})\**$")
SEMESTER = re.compile(r"^semester\s+([ivx]+|\d)$", re.I)
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
HEADER_CELLS = frozenset(
    {
        "title", "subject", "course title", "code", "cat", "cat.", "credit", "credits",
        "cr", "evaluation pattern", "evaluation", "l t p", "l-t-p",
    }
)  # fmt: skip
LTP = re.compile(r"^\[?\d+\]?\s*[-–— ]\s*\d+\s*[-–— ]\s*\d+$")
CREDIT = re.compile(r"^(?:\d{1,2}|P/F|\[\d\])$")
EVALUATION = re.compile(r"^\d{2}:\d{2}$")
#: A department tag: SCI, ENGG, HUM, PRJ, ECE, MEE, "CSE / ENGG"…
CATEGORY = re.compile(r"^[A-Z]{2,5}(?:\s*/\s*[A-Z]{2,5})?$")
SYLLABUS_HEAD = re.compile(r"^\s*(\d{2}[A-Z]{3}\d{3})\b(.*?)\bL-T-P-C\b")
SYLLABUS_START = re.compile(r"^\s*syllabus\b", re.I)
_BOOKS = r"(?:text\s*books?|text\s*book\(s\)|reference\s+books?|references?)"
SYLLABUS_END = re.compile(
    rf"^\s*(?:{_BOOKS}(?:\s*[/&,]\s*{_BOOKS})*\s*:?\s*$"
    r"|evaluation\s+(?:plan|pattern)\b|assessment\b.*\binternal\b)",
    re.I,
)


def _ends_syllabus(line: str) -> bool:
    return bool(SYLLABUS_END.match(line)) and line.strip()[:1].isupper()


def _clean(cell: str | None) -> str:
    text = (cell or "").replace("�", "-").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\*+$", "", text).strip()
    return re.sub(r"\s+-(?=\S)", "-", text)


def _lines(page) -> list[tuple[float, str]]:
    """The page's text as (y, line), words regrouped by baseline."""
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for x0, y0, _x1, y1, word, *_ in sorted(page.get_text("words"), key=lambda w: (w[1], w[0])):
        mid = (y0 + y1) / 2
        if rows and abs(rows[-1][0] - mid) <= 3:
            rows[-1][1].append((x0, word))
        else:
            rows.append((mid, [(x0, word)]))
    return [(y, " ".join(w for _, w in sorted(words))) for y, words in rows]


@dataclass
class Fragment:
    """One table row's fields. A course is one or two of these."""

    code: str | None = None
    title: str | None = None
    category: str | None = None
    ltp: str | None = None
    credits: str | None = None

    def fields(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v}

    def compatible(self, other: Fragment) -> bool:
        mine, theirs = self.fields(), other.fields()
        return all(mine[k] == v for k, v in theirs.items() if k in mine)

    def absorb(self, other: Fragment) -> None:
        for key, value in other.fields().items():
            setattr(self, key, getattr(self, key) or value)


def _fragment(cells: list[str]) -> Fragment | None:
    """A row's cells by what they look like, not by column index."""
    frag = Fragment()
    for cell in cells:
        if not cell:
            continue
        if m := CODE.match(cell):
            frag.code = frag.code or m.group(1)
        elif LTP.match(cell):
            frag.ltp = frag.ltp or re.sub(r"\s*[-–— ]\s*", "-", cell)
        elif CREDIT.match(cell):
            frag.credits = frag.credits or cell
        elif CATEGORY.match(cell):
            frag.category = frag.category or cell.replace(" ", "")
        elif EVALUATION.match(cell):
            continue
        elif re.search(r"[A-Za-z]{3}", cell):
            if frag.title is None or len(cell) > len(frag.title):
                frag.title = cell
    if not frag.fields():
        return None
    title = (frag.title or "").casefold()
    if title in HEADER_CELLS or title.startswith(("total", "cat ")):
        frag.title = None
        return frag if frag.code else None
    if frag.title and (frag.title[0] in "*@" or len(frag.title.split()) > 12):
        return None  # a footnote the table detector swept into the last row
    return frag


@dataclass
class Context:
    kind: str  # "semester" | "basket" | "skip"
    name: str
    number: int | None = None
    rows: list[Fragment] = field(default_factory=list)
    pending: list[Fragment] = field(default_factory=list)

    def add(self, frag: Fragment) -> None:
        prev = self.rows[-1] if self.rows else None
        continues = (
            prev is not None
            and not self.pending
            and prev.compatible(frag)
            and (
                (frag.code and not frag.title and not prev.code)
                or (frag.title and not frag.code and not prev.title)
                or (not frag.code and not frag.title)
            )
        )
        if continues:
            prev.absorb(frag)
        elif not frag.code and not frag.title:
            self.pending.append(frag)
        else:
            for early in self.pending:
                frag.absorb(early)
            self.pending = []
            self.rows.append(frag)


def _heading(text: str) -> Context | None:
    """A semester or elective-basket heading, or None."""
    text = _clean(text)
    if m := SEMESTER.match(text):
        token = m.group(1).casefold()
        number = ROMAN.get(token) or int(token)
        return Context("semester", f"Semester {number}", number)
    lowered = text.casefold()
    if len(text.split()) > 9 or text.startswith("*") or CODE.match(text.split(" ")[0] or ""):
        return None
    if "other branches" in lowered:
        return Context("skip", text)
    if "free elective" in lowered or "value programme" in lowered:
        return Context("skip", text)
    if "elective" in lowered:
        return Context("basket", text)
    return None


def _first_syllabus_page(doc) -> int:
    for number, page in enumerate(doc):
        if any(SYLLABUS_HEAD.match(line) for _, line in _lines(page)):
            return number
    return doc.page_count


def read_tables(doc) -> list[Context]:
    """Every course row, in reading order, under the heading above it."""
    contexts: list[Context] = []
    current: Context | None = None
    for number in range(_first_syllabus_page(doc)):
        page = doc[number]
        tables = page.find_tables().tables
        boxes = [t.bbox for t in tables]
        items: list[tuple[float, str, object]] = []
        for y, line in _lines(page):
            if not any(b[1] - 1 <= y <= b[3] + 1 for b in boxes):
                items.append((y, "line", line))
        for table in tables:
            for row, cells in zip(table.rows, table.extract(), strict=False):
                items.append((row.bbox[1], "row", [_clean(c) for c in cells]))
        for _y, kind, payload in sorted(items, key=lambda i: i[0]):
            if kind == "line":
                if heading := _heading(payload):  # type: ignore[arg-type]
                    current = heading
                    contexts.append(current)
                continue
            cells: list[str] = payload  # type: ignore[assignment]
            first = next((c for c in cells if c), "")
            heading = _heading(first) if first and sum(bool(c) for c in cells) == 1 else None
            if heading:
                current = heading
                contexts.append(current)
                continue
            if current is None or current.kind == "skip":
                continue
            if frag := _fragment(cells):
                current.add(frag)
    return contexts


def read_syllabi(doc) -> dict[str, dict]:
    """code -> {"heading", "units", "page"}; `page` is 1-based, where it starts."""
    lines: list[tuple[int, str]] = []
    for number in range(_first_syllabus_page(doc), doc.page_count):
        lines += [(number + 1, line) for _, line in _lines(doc[number])]
    found: dict[str, dict] = {}
    starts = [(i, m) for i, (_, line) in enumerate(lines) if (m := SYLLABUS_HEAD.match(line))]
    for n, (i, match) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        body = [line for _, line in lines[i + 1 : end]]
        begin = next((k for k, line in enumerate(body) if SYLLABUS_START.match(line)), None)
        if begin is None:
            units = body
        else:
            stop = next(
                (k for k, line in enumerate(body[begin + 1 :], begin + 1) if _ends_syllabus(line)),
                len(body),
            )
            units = body[begin + 1 : stop]
        code = match.group(1)
        entry = found.setdefault(
            code, {"heading": _clean(match.group(2)), "units": "", "page": lines[i][0]}
        )
        entry["units"] = (entry["units"] + "\n" + "\n".join(units)).strip()
    return found


def _slot(title: str) -> str | None:
    lowered = title.casefold()
    if "professional elective" in lowered:
        return "professional"
    if "free elective" in lowered:
        return "free"
    if "value" in lowered and "program" in lowered:
        return "value"
    return None


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.casefold().replace("&", " and ")).replace(" and ", " ")


def read_curriculum(pdf: Path) -> tuple[dict, list[str]]:
    """{"semesters": [...], "electives": [...], "pages": n}, plus warnings."""
    import pymupdf  # the `sync` extra

    doc = pymupdf.open(pdf)
    warnings: list[str] = []
    contexts = read_tables(doc)
    syllabi = read_syllabi(doc)

    def course(frag: Fragment) -> dict:
        record = {
            "code": frag.code,
            "title": frag.title,
            "category": frag.category,
            "ltp": frag.ltp,
            "credits": frag.credits,
            "syllabus": None,
            "syllabus_page": None,
        }
        syllabus = syllabi.get(frag.code or "")
        if syllabus is None:
            warnings.append(f"{frag.code} {frag.title}: no syllabus page")
            return record
        if syllabus["heading"] and _norm(syllabus["heading"]) != _norm(frag.title or ""):
            warnings.append(
                f"{frag.code}: table says {frag.title!r}, syllabus says {syllabus['heading']!r}"
            )
        record["syllabus"] = syllabus["units"] or None
        record["syllabus_page"] = syllabus["page"]
        return record

    semesters: dict[int, dict] = {}
    baskets: list[dict] = []
    for ctx in contexts:
        if ctx.kind == "semester" and ctx.number:
            sem = semesters.setdefault(
                ctx.number, {"number": ctx.number, "courses": [], "slots": []}
            )
            for frag in ctx.rows:
                if frag.code and frag.title:
                    sem["courses"].append(course(frag))
                elif frag.title and (kind := _slot(frag.title)):
                    sem["slots"].append(
                        {"kind": kind, "title": frag.title, "credits": frag.credits}
                    )
                else:
                    warnings.append(f"semester {ctx.number}: unplaced row {frag.fields()}")
        elif ctx.kind == "basket":
            rows = [course(f) for f in ctx.rows if f.code and f.title]
            if rows:
                baskets.append({"name": ctx.name, "courses": rows})
    if sorted(semesters) != list(range(1, 9)):
        warnings.append(f"semesters found: {sorted(semesters)} (expected 1-8)")
    return (
        {
            "semesters": [semesters[n] for n in sorted(semesters)],
            "electives": baskets,
            "pages": doc.page_count,
        },
        warnings,
    )
