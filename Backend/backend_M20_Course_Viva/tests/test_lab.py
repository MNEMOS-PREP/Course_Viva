"""A lab viva walks the experiment (FR-20.19): aim, principle, procedure,
observations, result, precautions, sources of error — the order a lab
examiner asks in, drawn only from what the manual states."""

from __future__ import annotations

import re

import pytest

from backend_M20_Course_Viva import bank, llm
from backend_M20_Course_Viva.llm import JOB_BANK, LLMResult

from .conftest import as_student
from .stubs import StubLLM, deck, pages_of

COURSE = "btech-cse-2023:23CSE201"
ME = as_student("student-lab")

#: An experiment over two pages, every step a heading.
MANUAL = [
    "Aim: To simulate the FIFO and LRU page replacement algorithms and compare their page faults.\n"
    "Principle: When memory is full, a page replacement algorithm chooses which page to evict so "
    "that a new page can be loaded.\n"
    "Procedure: Read the reference string, simulate each algorithm with three frames, and count a "
    "fault whenever the page is not in memory.",
    "Observations: The fault count is recorded for each algorithm after every reference in the "
    "string.\n"
    "Result: LRU produced fewer page faults than FIFO for the given reference string.\n"
    "Precautions: Reset the frames before each algorithm is simulated so that no page is carried "
    "over.\n"
    "Sources of error: A reference string that is too short may hide the difference between the "
    "two algorithms.",
]

#: The model's question for each heading, and the family it gives it.
ASKS = {
    "aim": ("What does the experiment set out to compare?", "aim"),
    "principle": ("Why does a page replacement algorithm run at all?", "explain"),
    "procedure": ("How is each algorithm simulated?", "procedure"),
    "observations": ("What is recorded while the string is read?", "observation"),
    "result": ("Which algorithm gave fewer page faults?", "result"),
    "precautions": ("What must be done before each simulation?", "precaution"),
    "sources of error": ("What can a short reference string hide?", "error"),
}
WALK = ["principle", "procedure", "observations", "result", "precautions", "sources of error"]


class LabModel(StubLLM):
    """One question per heading, handed back last step first — so the order
    a lab viva asks in is the viva's doing, not the model's."""

    def __init__(self, *, skip: set[str] = frozenset(), extra: bool = False):
        super().__init__()
        self.skip = skip
        self.extra = extra

    def structured(self, *, job: str, system: str, user: str, schema: dict) -> LLMResult:
        if job != JOB_BANK:
            return super().structured(job=job, system=system, user=user, schema=schema)
        self.calls.append({"job": job, "user": user})
        questions = []
        for number, text in pages_of(user).items():
            for line in text.splitlines():
                head, _, body = line.partition(": ")
                head = head.strip().casefold()
                if head not in ASKS or head in self.skip:
                    continue
                question, family = ASKS[head]
                point = " ".join(body.split()[:7])
                questions.append(
                    {
                        "page": number,
                        "length": "short",
                        "family": family,
                        "question": question,
                        "quote": body,
                        "answer_points": [{"point": point, "probe": "What else?"}],
                        "hint": "Think about what the experiment measures.",
                        "difficulty": 1,
                    }
                )
                if head == "procedure" and self.extra:
                    questions.append(
                        {**questions[-1], "question": "How many frames does each simulation use?"}
                    )
        return LLMResult(ok=True, job=job, model="stub-lab", data={"questions": questions[::-1]})


@pytest.fixture
def lab_model():
    def use(**kw) -> LabModel:
        stub = LabModel(**kw)
        llm.set_llm(stub)
        return stub

    yield use
    llm.set_llm(None)


def _upload(client):
    response = client.post(
        f"/v1/library/courses/{COURSE}/materials",
        files={"file": ("lab6.pptx", deck(MANUAL), "application/octet-stream")},
        data={"kind": "lab_manual", "unit": "Lab 6", "visibility": "private"},
        headers=ME,
    )
    assert response.status_code == 201, response.text
    return response.json()["material"]


def _sit(client, questions: int, style: str = "lab") -> tuple[dict, list[str]]:
    """A whole viva, every answer right; the questions in the order asked."""
    state = client.post(
        "/v1/vivas",
        json={"course_id": COURSE, "questions": questions, "style": style, "mode": "typed"},
        headers=ME,
    ).json()
    while state["status"] == "live":
        state = client.post(
            f"/v1/vivas/{state['id']}/answer",
            json={"text": "A page is evicted when memory is full."},
            headers=ME,
        ).json()
    asked = [re.sub(r"^(Next: |Now, |Moving on\. |Alright\. )", "", t["text"])
             for t in state["turns"] if t["kind"] == "question"]  # fmt: skip
    return state, asked


def _step(text: str) -> str:
    """Which heading a question asked about."""
    for head, (question, _family) in ASKS.items():
        if text.casefold() == question.casefold():
            return head
    return "procedure" if "frames" in text else text


def test_a_lab_viva_walks_the_experiment_in_order(client, lab_model):
    lab_model()
    _upload(client)
    state, asked = _sit(client, questions=6)
    assert state["style"] == "lab"
    assert [_step(q) for q in asked] == WALK, "principle → … → sources of error"


def test_it_opens_on_the_aim_and_says_it_is_a_lab_viva(client, lab_model):
    lab_model()
    _upload(client)
    state, _asked = _sit(client, questions=6)
    greeting, warmup = state["turns"][0]["text"], state["turns"][1]["text"]
    assert "lab viva on Lab 6" in greeting
    assert "aim of Lab 6" in warmup


def test_the_aim_is_not_asked_again_while_another_step_is_left(client, lab_model):
    """The warm-up asked the aim: a banked aim question waits until a second
    round of the steps is used up, then comes last."""
    lab_model(extra=True)
    _upload(client)
    _state, asked = _sit(client, questions=8)
    steps = [_step(q) for q in asked]
    assert len(set(asked)) == 8
    assert steps[:6] == WALK
    assert steps[6] == "procedure", "round two of the steps before the aim"
    assert steps[7] == "aim"


def test_a_step_the_manual_does_not_state_is_skipped(client, lab_model):
    lab_model(skip={"observations", "precautions"})
    _upload(client)
    _state, asked = _sit(client, questions=4)
    assert [_step(q) for q in asked] == ["principle", "procedure", "result", "sources of error"]


def test_the_report_names_each_question_s_step(client, lab_model):
    lab_model()
    _upload(client)
    state, _asked = _sit(client, questions=6)
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["viva"]["style"] == "lab"
    assert [i["stage"] for i in report["items"]] == WALK


def test_a_course_viva_on_the_same_manual_has_no_steps(client, lab_model):
    lab_model()
    _upload(client)
    state, asked = _sit(client, questions=6, style="course")
    assert state["style"] == "course"
    assert "This is your viva on Lab 6" in state["turns"][0]["text"]
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert all(i["stage"] is None for i in report["items"])


def test_a_style_is_course_or_lab(client, lab_model):
    lab_model()
    _upload(client)
    response = client.post("/v1/vivas", json={"course_id": COURSE, "style": "exam"}, headers=ME)
    assert response.status_code == 422


def test_lab_headings_by_rule_have_their_steps_families():
    """With no model, a manual's headings still give one question per step."""
    families = {q.text: q.family for page in MANUAL for q in bank.by_rule(page, "m1", 1)}
    assert families == {
        "What is the aim of this experiment?": "aim",
        "What is the principle behind this experiment?": "explain",
        "How do you carry out this experiment?": "procedure",
        "What do you observe in this experiment?": "observation",
        "What result does this experiment give?": "result",
        "What precautions does this experiment need?": "precaution",
        "What are the sources of error in this experiment?": "error",
    }


def test_every_family_the_model_may_use_is_in_a_step_or_is_the_aim():
    in_steps = set().union(*(families for _name, families in bank.LAB_STAGES))
    assert set(bank.FAMILIES) - in_steps == {"aim"}
