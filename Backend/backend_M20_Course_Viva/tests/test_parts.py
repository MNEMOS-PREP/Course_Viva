"""A long document, ten pages at a time, and no page lost (2026-10-28).

The user: "if a user uploads a long PDF, how do you chunk it so that no loss
happens? Give him 10 pages at a time; while he finishes one, prepare the
next." Measured on a real 59-page slide deck: a slide is short, and the old
200-character floor dropped real slides silently; one call per page was 59
calls for one deck.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from backend_M20_Course_Viva import bank, llm, materials
from backend_M20_Course_Viva.models import BankPage, Material, Question

from .conftest import as_student
from .stubs import StubLLM, deck, pages_of

COURSE = "btech-cse-2023:23CSE201"
ME = as_student("student-parts")


def slide(n: int) -> str:
    """A short slide that is still a whole idea (~150 characters, under the old 200 floor)."""
    return (
        f"Slide {n} idea: when memory is full a page is evicted, and rule {n} decides which one "
        f"goes. Rule {n} keeps the frames busy and the fault count low."
    )


#: 25 pages: two of them only pictures (no text), one a title.
PICTURES = {6, 17}
TITLE = 12


def long_deck() -> bytes:
    pages = []
    for n in range(1, 26):
        if n in PICTURES:
            pages.append("")
        elif n == TITLE:
            pages.append("Part Two")
        else:
            pages.append(slide(n))
    return deck(pages)


@pytest.fixture
def model():
    stub = StubLLM()
    llm.set_llm(stub)
    yield stub
    llm.set_llm(None)


def _material(session, by="student-parts") -> Material:
    return materials.add_file(
        session, course_id=COURSE, data=long_deck(), filename="td-learning.pptx", added_by=by,
        kind="slides", visibility="private",
    ).material  # fmt: skip


def test_a_part_is_its_ten_pages():
    assert bank.part_of(1) == (1, 10)
    assert bank.part_of(10) == (1, 10)
    assert bank.part_of(11) == (11, 20)
    assert bank.part_of(59) == (51, 60)


def test_a_part_is_banked_in_one_call_and_every_page_with_text_gets_a_question(session, model):
    material = _material(session)
    bank.ensure(session, material.id, 3, llm=model)
    calls = [c for c in model.calls if c["job"] == "viva_bank"]
    assert len(calls) == 1, "ten pages, one call"
    assert sorted(pages_of(calls[0]["user"])) == [1, 2, 3, 4, 5, 7, 8, 9, 10]
    asked = {q.page for q in bank.asked_from(session, [(material.id, p) for p in range(1, 11)])}
    assert asked == {1, 2, 3, 4, 5, 7, 8, 9, 10}, "no page with text is lost"
    # The next part is untouched until it is needed.
    assert session.get(BankPage, (material.id, 11)) is None


def test_a_short_slide_is_not_dropped(session, model):
    """A 150-character slide is a whole idea; the old floor of 200 dropped it."""
    assert len(slide(3)) < 200
    material = _material(session)
    bank.ensure(session, material.id, 3, llm=model)
    assert bank.asked_from(session, [(material.id, 3)])


def test_a_page_the_model_skips_gets_a_call_of_its_own(session):
    class Skips(StubLLM):
        def structured(self, **kw):
            result = super().structured(**kw)
            if kw["job"] == "viva_bank" and len(pages_of(kw["user"])) > 1:
                result.data["questions"] = [q for q in result.data["questions"] if q["page"] != 4]
            return result

    model = Skips()
    material = _material(session)
    bank.ensure(session, material.id, 1, llm=model)
    calls = [c for c in model.calls if c["job"] == "viva_bank"]
    assert len(calls) == 2 and sorted(pages_of(calls[1]["user"])) == [4]
    assert "MUST COVER (at least one question each): 4" in calls[1]["user"]
    assert bank.asked_from(session, [(material.id, 4)])


def test_a_page_still_left_out_is_written_by_rule_never_dropped(session):
    class NeverPageFour(StubLLM):
        def structured(self, **kw):
            result = super().structured(**kw)
            if kw["job"] == "viva_bank":
                result.data["questions"] = [q for q in result.data["questions"] if q["page"] != 4]
            return result

    material = _material(session)
    bank.ensure(session, material.id, 1, llm=NeverPageFour())
    page_four = bank.asked_from(session, [(material.id, 4)])
    assert page_four and all(q.generated_by == bank.RULES for q in page_four)


def test_a_quote_on_another_page_of_the_call_is_given_its_true_page(session):
    """A model that miscounts a marker still quoted the material."""

    class Miscounts(StubLLM):
        def structured(self, **kw):
            result = super().structured(**kw)
            if kw["job"] == "viva_bank":
                for q in result.data["questions"]:
                    if q["page"] == 2:
                        q["page"] = 3
            return result

    material = _material(session)
    bank.ensure(session, material.id, 1, llm=Miscounts())
    page_two = bank.asked_from(session, [(material.id, 2)])
    assert page_two and all("Slide 2 idea" in q.quote for q in page_two)


def test_the_scope_lists_parts_pictures_and_readiness(client, engine, model):
    with Session(engine) as session:
        material = _material(session)
        material_id = material.id
    scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
    parts = next(m for m in scope["materials"] if m["id"] == material_id)["parts"]
    assert [(p["first"], p["last"]) for p in parts] == [(1, 10), (11, 20), (21, 25)]
    assert parts[0]["picture_pages"] == [6]
    assert parts[1]["picture_pages"] == [TITLE, 17], "a title is no more examinable than a picture"
    assert [p["ready"] for p in parts] == [False, False, False]


def _start_part(client, material_id: str, first: int, last: int, questions=3):
    response = client.post(
        "/v1/vivas",
        json={"course_id": COURSE, "material_ids": [material_id], "pages": {material_id: [first, last]},
              "questions": questions},
        headers=ME,
    )  # fmt: skip
    assert response.status_code == 201, response.text
    return response.json()


def test_a_part_viva_prepares_the_next_part_and_offers_it(client, engine, model):
    with Session(engine) as session:
        material_id = _material(session).id
    state = _start_part(client, material_id, 1, 10)
    viva_id = state["id"]
    while state["status"] == "live":
        state = client.post(
            f"/v1/vivas/{viva_id}/answer",
            json={"text": "A page is evicted when memory is full."},
            headers=ME,
        ).json()
    close = state["turns"][-1]
    assert close["kind"] == "close" and "pages 11 to 20" in close["text"]
    assert state["next_part"]["first"] == 11 and state["next_part"]["last"] == 20
    assert state["next_part"]["ready"] is True, "banked while part one ran"
    with Session(engine) as session:
        asked = session.exec(select(Question.page).where(Question.material_id == material_id)).all()
    assert {p for p in asked if 1 <= p <= 10} and {p for p in asked if 11 <= p <= 20}

    report = client.get(f"/v1/vivas/{viva_id}/report", headers=ME).json()
    assert report["coverage"]["first"] == 1 and report["coverage"]["picture_pages"] == [6]
    assert report["next_part"]["first"] == 11

    scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
    parts = next(m for m in scope["materials"] if m["id"] == material_id)["parts"]
    assert parts[0]["done"] is True and parts[1]["done"] is False and parts[1]["ready"] is True

    second = _start_part(client, material_id, 11, 20)
    assert second["status"] == "live"


def test_the_last_part_offers_nothing_after_it(client, engine, model):
    with Session(engine) as session:
        material_id = _material(session).id
    state = _start_part(client, material_id, 21, 25)
    while state["status"] == "live":
        state = client.post(
            f"/v1/vivas/{state['id']}/answer", json={"text": "I don't know."}, headers=ME
        ).json()
    assert state["next_part"] is None
    assert "pages" not in state["turns"][-1]["text"].split("report")[-1]


def test_a_document_of_ten_pages_or_fewer_has_no_parts(client, engine, model):
    with Session(engine) as session:
        materials.add_file(
            session, course_id=COURSE, data=deck([slide(1), slide(2)]), filename="short.pptx",
            added_by="student-parts", kind="slides", visibility="private",
        )  # fmt: skip
    scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
    assert all(m["parts"] == [] for m in scope["materials"] if m["pages"] <= 10)


def test_the_examiner_says_which_pages(client, engine, model):
    with Session(engine) as session:
        material_id = _material(session).id
    state = _start_part(client, material_id, 11, 20)
    assert "pages 11 to 20" in state["turns"][0]["text"]
    assert state["part"] == {"material_id": material_id, "first": 11, "last": 20}
    # The last part's span is the document's end, not the part's tenth page.
    last = _start_part(client, material_id, 21, 30)
    assert last["part"]["last"] == 25 and "pages 21 to 25" in last["turns"][0]["text"]


def test_ten_pages_of_pictures_are_passed_over(client, engine, model):
    pages = [slide(n) if not 11 <= n <= 20 else "" for n in range(1, 26)]
    with Session(engine) as session:
        material_id = materials.add_file(
            session, course_id=COURSE, data=deck(pages), filename="figures.pptx",
            added_by="student-parts", kind="slides", visibility="private",
        ).material.id  # fmt: skip
    state = _start_part(client, material_id, 1, 10)
    while state["status"] == "live":
        state = client.post(
            f"/v1/vivas/{state['id']}/answer", json={"text": "I don't know."}, headers=ME
        ).json()
    assert (state["next_part"]["first"], state["next_part"]["last"]) == (21, 25)
    assert "pages 21 to 25" in state["turns"][-1]["text"]
