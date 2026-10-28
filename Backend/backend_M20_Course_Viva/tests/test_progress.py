"""The student's progress over their vivas (progress.py): each measure now and
at first, its band and its way, strengths and what to work on — counted from
the answers, never scored by a model."""

from __future__ import annotations

import pytest

from backend_M20_Course_Viva import llm, progress, speaking

from .conftest import as_student
from .stubs import StubLLM, deck

COURSE = "btech-cse-2023:23CSE201"
ME = as_student("student-progress")
SOMEONE_ELSE = as_student("student-else")

#: Right, opened with the answer, a reason given, no fillers.
CLEAN = "A page is evicted when memory is full, because a new page needs a frame."
#: Right, but opened with fillers and said unsurely.
HESITANT = "Um, so I think, um, maybe a page is evicted when memory is full, you know."


@pytest.fixture
def model():
    stub = StubLLM()
    llm.set_llm(stub)
    yield stub
    llm.set_llm(None)


def _upload(client):
    response = client.post(
        f"/v1/library/courses/{COURSE}/materials",
        files={"file": ("lab6.pptx", deck(), "application/octet-stream")},
        data={"kind": "notes", "unit": "Unit 3", "visibility": "private"},
        headers=ME,
    )
    assert response.status_code == 201, response.text


def _sit(client, answer: str, headers=ME) -> dict:
    state = client.post(
        "/v1/vivas", json={"course_id": COURSE, "questions": 3}, headers=headers
    ).json()
    while state["status"] == "live":
        timing = {"spoken": True, "silence_ms": 2000, "duration_ms": 6000}
        state = client.post(
            f"/v1/vivas/{state['id']}/answer", json={"text": answer, "timing": timing},
            headers=headers,
        ).json()  # fmt: skip
    return state


def _measure(body: dict, key: str) -> dict:
    return next(m for m in body["measures"] if m["key"] == key)


def test_with_no_vivas_nothing_is_shown_as_a_zero(client, model):
    body = client.get("/v1/vivas/progress", headers=ME).json()
    assert body["vivas"] == 0 and body["answers"] == 0
    assert all(m["now"] is None and m["band"] is None for m in body["measures"])
    assert body["visual"]["measured"] is False and "later" in body["visual"]["note"]


def test_progress_reads_each_viva_s_answers(client, model):
    _upload(client)
    _sit(client, CLEAN)
    body = client.get("/v1/vivas/progress", headers=ME).json()
    assert body["vivas"] == 1 and body["answers"] == 3
    assert _measure(body, "right_first_time")["now"] == 1.0
    assert _measure(body, "direct")["now"] == 1.0
    assert _measure(body, "explains")["now"] == 1.0, "every long answer gave a reason"
    assert _measure(body, "fillers_per_100")["now"] == 0
    assert _measure(body, "wait_ms")["now"] == 2000
    assert _measure(body, "course_words")["now"] > 0.3
    assert _measure(body, "right_first_time")["band"] == "good"
    assert body["by_length"][0]["right"] == 3


def test_fillers_and_hesitations_are_what_to_work_on_with_a_tip(client, model):
    _upload(client)
    _sit(client, HESITANT)
    body = client.get("/v1/vivas/progress", headers=ME).json()
    fillers = _measure(body, "fillers_per_100")
    assert fillers["now"] > 6 and fillers["band"] == "work"
    assert _measure(body, "hedges_per_100")["band"] == "work"
    assert _measure(body, "direct")["now"] == 0
    work = {w["key"]: w for w in body["work_on"]}
    assert "fillers_per_100" in work and work["fillers_per_100"]["tip"]
    assert "hedges_per_100" in work and "direct" in work


def test_the_way_a_measure_is_moving_needs_more_vivas_than_the_window(client, model):
    _upload(client)
    for _ in range(3):
        _sit(client, HESITANT)
    assert (
        _measure(client.get("/v1/vivas/progress", headers=ME).json(), "fillers_per_100")[
            "direction"
        ]
        is None
    ), "three vivas: no 'at first' apart from 'now' yet"
    for _ in range(3):
        _sit(client, CLEAN)
    body = client.get("/v1/vivas/progress", headers=ME).json()
    fillers = _measure(body, "fillers_per_100")
    assert fillers["direction"] == "better" and fillers["now"] < fillers["first"]
    assert len(fillers["series"]) == 6 == len(body["series"])


def test_progress_is_the_student_s_own(client, model):
    _upload(client)
    _sit(client, CLEAN)
    assert client.get("/v1/vivas/progress", headers=SOMEONE_ELSE).json()["vivas"] == 0
    assert client.get("/v1/vivas/progress").status_code == 401


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [("right_first_time", 0.8, "good"), ("right_first_time", 0.6, "fair"),
     ("right_first_time", 0.2, "work"), ("fillers_per_100", 2, "good"),
     ("fillers_per_100", 9, "work"), ("wpm", 130, "good"), ("wpm", 100, "fair"),
     ("wpm", 220, "work"), ("wait_ms", None, None)],
)  # fmt: skip
def test_a_measure_s_band(key, value, expected):
    measure = next(m for m in progress.MEASURES if m.key == key)
    assert progress.band(measure, value) == expected


def test_hesitations_and_framing_are_counted_from_the_words():
    assert speaking.hedges_in("I think it is maybe LRU, probably.") == 3
    assert speaking.hedges_in("He thinks it is LRU.") == 0
    framed = speaking.framing(HESITANT)
    assert framed["direct"] is False and framed["reasons"] == 0
    framed = speaking.framing(CLEAN)
    assert framed["direct"] is True and framed["reasons"] == 1 and framed["sentences"] == 1
    long = " ".join(["word"] * 40) + "."
    assert speaking.framing(long)["run_on"] == 1


def test_a_measure_is_read_over_the_vivas_that_took_it(client, model):
    """Live: three typed vivas after spoken ones made pace "not measured yet"."""
    _upload(client)
    _sit(client, CLEAN)  # spoken: has a pace
    for _ in range(3):
        state = client.post(
            "/v1/vivas", json={"course_id": COURSE, "questions": 3}, headers=ME
        ).json()
        while state["status"] == "live":
            state = client.post(
                f"/v1/vivas/{state['id']}/answer", json={"text": CLEAN}, headers=ME
            ).json()
    pace = _measure(client.get("/v1/vivas/progress", headers=ME).json(), "wpm")
    assert pace["series"][-1] is None and pace["now"] is not None


def test_a_small_change_is_steady_not_a_way():
    words = next(m for m in progress.MEASURES if m.key == "words_per_sentence")
    assert progress._direction(words, 9.3, 9.2) == "steady"
    fillers = next(m for m in progress.MEASURES if m.key == "fillers_per_100")
    assert progress._direction(fillers, 6.0, 2.0) == "better"
    assert progress._direction(fillers, 2.0, 6.0) == "worse"
