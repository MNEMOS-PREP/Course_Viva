"""Pictures, read (reading.py): a slide that is a screenshot, an equation drawn
as an image, a scanned page — read once by the vision tier, then searched,
banked and cited like any page (the user, 2026-10-28: "add OCR or a vision
model, whichever does well")."""

from __future__ import annotations

import pymupdf
import pytest
from sqlmodel import Session, select

from backend_M20_Course_Viva import bank, llm, materials, reading, viva
from backend_M20_Course_Viva.llm import LLMResult
from backend_M20_Course_Viva.models import BankPage, Material, MaterialPage

from .conftest import as_student
from .stubs import StubLLM

COURSE = "btech-cse-2023:23CSE201"
ME = as_student("student-reading")

TEXT = (
    "Page replacement decides which page to evict when memory is full and a new page is "
    "needed. FIFO replaces the page that has been in memory the longest."
)
#: What the stub "reads" off a picture: the bank stub's points (evicted, full)
#: are in it, so a question can be written from it.
READ = (
    "TD update: V(S_t) <- V(S_t) + alpha [R_{t+1} + gamma V(S_{t+1}) - V(S_t)]. When memory "
    "is full a page is evicted, as the figure shows.\nFigure: a timeline of page frames."
)


def _pixmap(colour: tuple[int, int, int]) -> pymupdf.Pixmap:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 32, 32), False)
    pix.set_rect(pix.irect, colour)
    return pix


def pdf(pages: list[dict]) -> bytes:
    """A PDF: each page a dict of `text` (a box of it) and `picture` (a
    rectangle of the page covered by an image)."""
    document = pymupdf.open()
    for spec in pages:
        page = document.new_page(width=720, height=405)
        if spec.get("text"):
            page.insert_textbox(pymupdf.Rect(36, 36, 684, 200), spec["text"], fontsize=12)
        if spec.get("picture"):
            # A colour of its own: identical pictures are one image in a PDF,
            # and one on most pages is the template, not content.
            colour = (40 * len(document) % 256, 90, 160)
            page.insert_image(pymupdf.Rect(*spec["picture"]), pixmap=_pixmap(colour))
    return document.tobytes()


#: 1 text · 2 a full picture · 3 a title and a small logo · 4 a title over a
#: big picture · 5 blank.
DECK = [
    {"text": TEXT},
    {"picture": (20, 20, 700, 385)},
    {"text": "Part Two", "picture": (20, 360, 80, 395)},
    {"text": "Worked example", "picture": (20, 60, 700, 385)},
    {},
]


class Reads(StubLLM):
    """Reads every picture as `READ`; `script` replaces the first answers."""

    def __init__(self, script: list[LLMResult] | None = None):
        super().__init__()
        self.script = list(script or [])
        self.reads = 0

    def can(self, job: str) -> bool:
        return True

    def read_image(self, *, job: str, prompt: str, image_b64: str) -> LLMResult:
        self.reads += 1
        assert image_b64, "a picture was sent"
        if self.script:
            return self.script.pop(0)
        return LLMResult(ok=True, job=job, model="stub-vision", data={"text": READ})


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(reading, "PACE_S", 0.0)
    monkeypatch.setattr(reading.time, "sleep", lambda s: None)


def _material(session, pages=DECK, name="paging.pdf") -> Material:
    return materials.add_file(
        session, course_id=COURSE, data=pdf(pages), filename=name, added_by="student-reading",
        kind="slides", visibility="private",
    ).material  # fmt: skip


def test_the_pages_worth_reading_are_the_pictures(session):
    material = _material(session)
    assert reading.to_read(session, material) == [2, 4], "not the text, the logo or the blank"


def test_a_picture_page_is_read_once_for_everyone(session):
    material = _material(session)
    model = Reads()
    assert reading.read_material(session, material.id, llm=model) == 2
    row = session.get(MaterialPage, (material.id, 2))
    assert row.text == READ and row.read_by == "vision:stub-vision"
    assert reading.read_material(session, material.id, llm=model) == 0
    assert model.reads == 2, "read once"


def test_what_was_read_is_banked_cited_and_searched(client, engine):
    with Session(engine) as session:
        material_id = _material(session).id
        reading.read_material(session, material_id, llm=Reads())
        bank.ensure(session, material_id, 1, llm=StubLLM())
        asked = bank.asked_from(session, [(material_id, 2)])
        assert asked, "a question from the picture"
        assert viva.read_from_picture(session, material_id, 2)
        assert not viva.read_from_picture(session, material_id, 1)
    found = client.get("/v1/library/search", params={"q": "timeline"}, headers=ME).json()
    # Both pictures were read as the same words: both are found.
    assert sorted(p["page"] for p in found["pages"] if p["material_id"] == material_id) == [2, 4]


def test_a_page_banked_before_it_was_read_is_banked_again(session):
    material = _material(session)
    bank.ensure(session, material.id, 1, llm=StubLLM())
    title = session.get(BankPage, (material.id, 4))
    assert title is not None and title.questions == 0, "a title, too short to ask about"
    reading.read_material(session, material.id, llm=Reads())
    assert session.get(BankPage, (material.id, 4)) is None, "its banking is undone"
    bank.ensure(session, material.id, 1, llm=StubLLM())
    assert bank.asked_from(session, [(material.id, 4)])


def test_a_scan_is_examinable_once_its_pages_are_read(client, engine):
    """EC-20.5: a scanned lab manual was stored and left out of every viva."""
    scan = [{"picture": (20, 20, 700, 385)}, {"picture": (20, 20, 700, 385)}]
    with Session(engine) as session:
        material = _material(session, scan, "scan.pdf")
        assert material.text_status == "no_text"
        material_id = material.id
    llm.set_llm(StubLLM())
    try:
        assert client.post("/v1/vivas", json={"course_id": COURSE}, headers=ME).status_code == 422
        with Session(engine) as session:
            reading.read_material(session, material_id, llm=Reads())
            assert session.get(Material, material_id).text_status == "ok"
        started = client.post("/v1/vivas", json={"course_id": COURSE, "questions": 3}, headers=ME)
        assert started.status_code == 201, started.text
    finally:
        llm.set_llm(None)


def test_a_picture_with_nothing_to_study_is_kept_as_nothing(session):
    material = _material(session)
    model = Reads([LLMResult(ok=True, model="stub-vision", data={"text": "NOTHING"})])
    reading.read_material(session, material.id, llm=model)
    row = session.get(MaterialPage, (material.id, 2))
    assert row.text == "" and row.read_by, "kept, so it is not sent again"
    assert reading.to_read(session, material) == []


def test_a_rate_limited_read_waits_and_is_tried_again(session):
    material = _material(session)
    limited = LLMResult(
        ok=False, reason='HTTP 429: {"error":{"message":"Please try again in 7.26s."}}'
    )
    model = Reads([limited])
    assert reading.read_material(session, material.id, llm=model) == 2
    assert model.reads == 3


def test_a_model_that_does_not_answer_leaves_the_page_for_later(session):
    material = _material(session)
    model = Reads([LLMResult(ok=False, reason="HTTP 500: upstream")])
    assert reading.read_material(session, material.id, llm=model) == 0
    assert model.reads == 1, "the rest wait for the next time, not hammered now"
    assert reading.to_read(session, material) == [2, 4]


def test_with_no_vision_model_nothing_is_read_in_the_background(session, monkeypatch):
    material = _material(session)
    monkeypatch.setattr(llm, "get_llm", lambda **k: llm.NullLLM())
    assert reading.start(material.id) is False
    assert session.exec(select(MaterialPage).where(MaterialPage.read_by.is_not(None))).all() == []


@pytest.mark.parametrize(
    ("reason", "wait"),
    [("HTTP 429: Please try again in 7.26s.", 8.26), ("HTTP 429: try again in 500ms", 1.5),
     ("HTTP 429: rate limited", 30.0), ("HTTP 500: upstream", None), (None, None)],
)  # fmt: skip
def test_how_long_a_429_says_to_wait(reason, wait):
    assert (
        reading._wait_for(reason) == pytest.approx(wait)
        if wait
        else reading._wait_for(reason) is None
    )


def test_a_logo_on_every_page_is_the_template_not_a_picture(session):
    """Live: the university's logo, on 54 of 59 slides, made title slides look
    like pictures worth reading, and was read into the text."""
    logo = pymupdf.Rect(20, 360, 80, 395)
    pages = []
    document = pymupdf.open()
    shared = _pixmap((200, 200, 0))
    for n in range(6):
        page = document.new_page(width=720, height=405)
        page.insert_image(logo, pixmap=shared)
        if n == 2:
            page.insert_image(pymupdf.Rect(20, 20, 700, 340), pixmap=_pixmap((10, 120, 10)))
        elif n != 5:
            page.insert_textbox(pymupdf.Rect(36, 36, 684, 200), TEXT, fontsize=12)
        pages.append(page)
    skip = reading.furniture(document)
    assert len(skip) == 1
    assert reading._picture_share(document[5], skip) == 0, "a title and the logo"
    assert reading._picture_share(document[2], skip) > 0.8
    assert reading._body(document[2], skip).y1 < logo.y0, "the footer is cut away"
