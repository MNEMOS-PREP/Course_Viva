"""Ideas taken from other products (2026-10-28 research), each as a student
meets it: a second go at what was missed (NotebookLM reruns missed cards), a
deeper question after a right short answer (Sherpa probes a strong answer),
and what each ten pages are about on the start panel."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from backend_M20_Course_Viva import llm, materials

from .conftest import as_student
from .stubs import StubLLM, deck, pages_of

COURSE = "btech-cse-2023:23CSE201"
ME = as_student("student-practice")
SOMEONE_ELSE = as_student("student-else")
RIGHT = "A page is evicted when memory is full."
BLANK = "I don't know."


@pytest.fixture
def model():
    stub = StubLLM()
    llm.set_llm(stub)
    yield stub
    llm.set_llm(None)


def _upload(client, data=None):
    response = client.post(
        f"/v1/library/courses/{COURSE}/materials",
        files={"file": ("lab6.pptx", data or deck(), "application/octet-stream")},
        data={"kind": "notes", "unit": "Unit 3", "visibility": "private"},
        headers=ME,
    )
    assert response.status_code == 201, response.text
    return response.json()["material"]


def _sit(client, answers: list[str], **body) -> dict:
    """A viva start to finish: the warm-up, then `answers` in turn."""
    state = client.post(
        "/v1/vivas", json={"course_id": COURSE, "questions": 3, **body}, headers=ME
    ).json()
    state = _answer(client, state, "It is about page replacement.")
    queue = list(answers)
    while state["status"] == "live":
        state = _answer(client, state, queue.pop(0) if queue else RIGHT)
    return state


def _answer(client, state, text):
    response = client.post(f"/v1/vivas/{state['id']}/answer", json={"text": text}, headers=ME)
    assert response.status_code == 200, response.text
    return response.json()


# ── A second go at what was missed ──────────────────────────────────────────


def test_a_second_go_asks_only_what_was_not_right_first_time(client, model):
    _upload(client)
    # First question: blank twice (taught). Second: right. Third: blank twice.
    first = _sit(client, [BLANK, BLANK, RIGHT, BLANK, BLANK])
    report = client.get(f"/v1/vivas/{first['id']}/report", headers=ME).json()
    missed = [i["question"] for i in report["items"] if i["status"] != "correct" or i["help"]]
    assert report["viva"]["missed"] == len(missed) == 2

    again = client.post(
        "/v1/vivas", json={"course_id": COURSE, "retry_of": first["id"]}, headers=ME
    )
    assert again.status_code == 201, again.text
    state = again.json()
    assert [t["kind"] for t in state["turns"]] == ["greeting", "question"], "no warm-up"
    assert "second go at the 2 questions" in state["turns"][0]["text"]
    assert state["target"] == 2
    asked = [state["turns"][-1]["text"]]
    while state["status"] == "live":
        state = _answer(client, state, RIGHT)
        asked += [t["text"] for t in state["turns"] if t["kind"] == "question"][len(asked) :]
    assert [viva_question(a) for a in asked] == [viva_question(m) for m in missed]
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["viva"]["retry_of"] == first["id"]
    assert client.get("/v1/vivas", headers=ME).json()[0]["retry"] is True


def viva_question(text: str) -> str:
    """The question without the examiner's lead-in ("Next: ", "Now, ")."""
    for lead in ("Next: ", "Now, ", "Moving on. ", "Alright. ", "And "):
        if text.startswith(lead):
            text = text[len(lead) :]
    return text[:1].upper() + text[1:]


def test_a_viva_with_nothing_missed_has_no_second_go(client, model):
    _upload(client)
    first = _sit(client, [RIGHT, RIGHT, RIGHT])
    report = client.get(f"/v1/vivas/{first['id']}/report", headers=ME).json()
    assert report["viva"]["missed"] == 0
    again = client.post(
        "/v1/vivas", json={"course_id": COURSE, "retry_of": first["id"]}, headers=ME
    )
    assert again.status_code == 422 and "right first time" in again.json()["detail"]


def test_a_second_go_is_only_at_your_own_viva(client, model):
    _upload(client)
    first = _sit(client, [BLANK, BLANK])
    again = client.post(
        "/v1/vivas", json={"course_id": COURSE, "retry_of": first["id"]}, headers=SOMEONE_ELSE
    )
    assert again.status_code == 404


# ── A right short answer is followed deeper ─────────────────────────────────


class ShortThenLong(StubLLM):
    """Each page: a short question on its first sentence, and a long one on
    the same page."""

    def structured(self, **kw):
        result = super().structured(**kw)
        if kw["job"] != "viva_bank":
            return result
        out = []
        for number, text in pages_of(kw["user"]).items():
            first = text.split(". ")[0] + "."
            out.append(
                {
                    "page": number,
                    "family": "definition",
                    "question": f"What happens on page {number} first?",
                    "quote": first,
                    "answer_points": [{"point": "the page is evicted", "probe": "Which?"}],
                    "hint": "Think about memory.",
                    "difficulty": 1,
                }
            )
            out.append({**out[-1], "question": f"Why does page {number} matter so much?", "family": "explain",
                        "answer_points": [{"point": "the page is evicted", "probe": "Which?"},
                                          {"point": "memory is full", "probe": "When?"}]})  # fmt: skip
        result.data["questions"] = out
        return result


def test_a_right_short_answer_is_followed_by_the_why_on_the_same_page(client):
    llm.set_llm(ShortThenLong())
    try:
        _upload(client)
        state = client.post(
            "/v1/vivas", json={"course_id": COURSE, "questions": 4}, headers=ME
        ).json()
        state = _answer(client, state, "It is about page replacement.")
        first = state["turns"][-1]["text"]
        assert first.startswith("What happens on page")
        page = first.split("page ")[1].split(" ")[0]
        state = _answer(client, state, "The page is evicted.")
        follow = state["turns"][-1]
        assert follow["kind"] == "question"
        assert follow["text"] == f"And why does page {page} matter so much?", follow["text"]
        # Wrong, then: the walk goes on as before, not deeper.
        state = _answer(client, state, BLANK)
        state = _answer(client, state, BLANK)
        assert not state["turns"][-1]["text"].startswith("And ")
    finally:
        llm.set_llm(None)


# ── What ten pages are about ────────────────────────────────────────────────


def test_each_part_says_what_it_is_about_from_its_pages(client, engine, model):
    body = (
        "When memory is full a page is evicted, and the replacement rule decides which one "
        "goes; the rule keeps the frames busy and the fault count low for the program."
    )
    titles = ["Temporal Difference", "Monte Carlo methods", "SARSA", "Q-learning", "SARSA"]
    pages = [f"{titles[n % 5]}\n{body}" for n in range(12)]
    with Session(engine) as session:
        material_id = materials.add_file(
            session, course_id=COURSE, data=deck(pages), filename="rl.pptx",
            added_by="student-practice", kind="slides", visibility="private",
        ).material.id  # fmt: skip
    scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
    parts = next(m for m in scope["materials"] if m["id"] == material_id)["parts"]
    assert parts[0]["topics"] == [
        "Temporal Difference",
        "Monte Carlo methods",
        "SARSA",
        "Q-learning",
    ]
    assert parts[1]["topics"] == ["Temporal Difference", "Monte Carlo methods"]
