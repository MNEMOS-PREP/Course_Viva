"""A viva's results reach the skill graph, M04, behind consent (FR-20.20;
skill_graph.py). M04 is faked here by what it answers; the shapes sent are
M04's own `ArtifactIn` / `ObservationIn`."""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session

from backend_M20_Course_Viva import llm, skill_graph
from backend_M20_Course_Viva.models import Viva

from .conftest import as_student
from .stubs import StubLLM, deck

COURSE = "btech-cse-2023:23CSE201"
STUDENT = str(uuid.uuid4())
ME = as_student(STUDENT)
RIGHT = "A page is evicted when memory is full, because a new page needs a frame."

CONCEPTS = {
    "concepts": [
        {"id": "concept:page_replacement", "name": "Page Replacement",
         "aliases": ["page replacement", "lru", "fifo", "belady's anomaly"]},
        {"id": "concept:answer_structuring", "name": "Answer Structuring", "aliases": []},
        {"id": "concept:deadlocks", "name": "Deadlocks", "aliases": ["deadlock"]},
    ]
}  # fmt: skip


class FakeM04:
    def __init__(self, *, consent: bool = True, down: bool = False):
        self.consent, self.down = consent, down
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method, path, body, headers):
        if self.down:
            raise skill_graph.Unreachable("ConnectionRefusedError")
        self.calls.append((method, path, body))
        assert headers.get("X-Candidate-Id") in (None, STUDENT)
        if path == "/v1/concepts":
            return CONCEPTS
        if path.endswith("/consent?purpose=practice"):
            return [{"consent_id": str(uuid.uuid4()), "active": True}] if self.consent else []
        if path.endswith("/artifacts"):
            return {"artifact_id": str(uuid.uuid4()), "checksum": "c0ffee"}
        if path.endswith("/observations"):
            return [{"recorded": True} for _ in body["observations"]]
        raise AssertionError(path)

    def posted(self, suffix: str) -> list[dict]:
        return [
            body for method, path, body in self.calls if method == "POST" and path.endswith(suffix)
        ]


@pytest.fixture
def m04(monkeypatch):
    def use(**kw) -> FakeM04:
        fake = FakeM04(**kw)
        monkeypatch.setattr(skill_graph, "_request", fake)
        monkeypatch.setattr(skill_graph, "_concepts", None)
        return fake

    return use


@pytest.fixture(autouse=True)
def model():
    llm.set_llm(StubLLM())
    yield
    llm.set_llm(None)


def _sit(client, headers=ME) -> dict:
    response = client.post(
        f"/v1/library/courses/{COURSE}/materials",
        files={"file": ("lab6.pptx", deck(), "application/octet-stream")},
        data={"kind": "notes", "visibility": "private"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    state = client.post(
        "/v1/vivas", json={"course_id": COURSE, "questions": 3}, headers=headers
    ).json()
    while state["status"] == "live":
        state = client.post(
            f"/v1/vivas/{state['id']}/answer", json={"text": RIGHT}, headers=headers
        ).json()
    return state


def test_an_ended_viva_reaches_the_skill_graph_with_consent(client, engine, m04):
    fake = m04()
    state = _sit(client)
    artifact = fake.posted("/artifacts")
    assert len(artifact) == 1 and artifact[0]["artifact_type"] == "viva_answers"
    assert RIGHT in artifact[0]["content"], "the student's own words are the evidence"
    batch = fake.posted("/observations")[0]["observations"]
    by_concept = {o["concept_id"]: o for o in batch}
    assert set(by_concept) == {"concept:page_replacement", "concept:answer_structuring"}
    assert by_concept["concept:page_replacement"]["outcome"] == 1.0, "right first time"
    assert all(o["kind"] == "answer_scored" and o["response_model"] == "none" for o in batch)
    assert all(o["session_id"] == str(uuid.UUID(state["id"])) for o in batch)
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["viva"]["skill_graph"]["sent"] == 2
    assert len(fake.posted("/observations")) == 1, "sent once, not again on reading the report"


def test_without_consent_nothing_is_sent_and_the_report_says_why(client, m04):
    fake = m04(consent=False)
    state = _sit(client)
    assert fake.posted("/artifacts") == [] and fake.posted("/observations") == []
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["viva"]["skill_graph"]["sent"] == 0
    assert "agreed" in report["viva"]["skill_graph"]["why"]


def test_a_student_not_from_the_platform_is_not_sent(client, m04):
    fake = m04()
    state = _sit(client, headers=as_student("dev-student"))
    assert fake.calls == []
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=as_student("dev-student")).json()
    assert "platform" in report["viva"]["skill_graph"]["why"]


def test_m04_down_is_tried_again_when_the_report_is_read(client, engine, m04):
    m04(down=True)
    state = _sit(client)
    with Session(engine) as session:
        assert session.get(Viva, state["id"]).scope["skill_graph"]["retry"] is True
    fake = m04()
    client.get(f"/v1/vivas/{state['id']}/report", headers=ME)
    assert len(fake.posted("/observations")) == 1
    with Session(engine) as session:
        assert session.get(Viva, state["id"]).scope["skill_graph"]["sent"] == 2


def test_a_question_is_on_the_concept_its_words_name():
    names = [
        {"id": c["id"], "names": sorted({n.casefold() for n in [c["name"], *c["aliases"]] if len(n) >= 3},
                                        key=len, reverse=True)}
        for c in CONCEPTS["concepts"]
    ]  # fmt: skip

    class Q:
        def __init__(self, text, quote="", points=()):
            self.text, self.quote = text, quote
            self.answer_points = [{"point": p, "probe": ""} for p in points]

    assert skill_graph.concept_for(Q("Why does FIFO suffer from Belady's anomaly?"), names) == (
        "concept:page_replacement"
    )
    assert skill_graph.concept_for(Q("When does a deadlock occur?"), names) == "concept:deadlocks"
    assert skill_graph.concept_for(Q("What is the TD error?"), names) is None
