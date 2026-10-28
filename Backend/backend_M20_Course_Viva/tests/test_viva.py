"""A viva, through the API: scope, the warm-up, every path through a question,
the report, and who may see what (FR-20.13, 20.15, 20.16, 20.18)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from backend_M20_Course_Viva import llm, viva
from backend_M20_Course_Viva.models import MaterialPage, Question

from .conftest import as_curator, as_student
from .stubs import StubLLM, deck

COURSE = "btech-cse-2023:23CSE201"
ME = as_student("student-me")
SOMEONE_ELSE = as_student("student-else")


@pytest.fixture
def model():
    stub = StubLLM()
    llm.set_llm(stub)
    yield stub
    llm.set_llm(None)


def _upload(client, headers=ME, data: bytes | None = None, name="lab6.pptx", visibility="private"):
    response = client.post(
        f"/v1/library/courses/{COURSE}/materials",
        files={"file": (name, data or deck(), "application/octet-stream")},
        data={"kind": "lab_manual", "unit": "Lab 6", "visibility": visibility},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["material"]


def _start(client, headers=ME, **body):
    return client.post(
        "/v1/vivas", json={"course_id": COURSE, "questions": 3, **body}, headers=headers
    )


def _say(client, viva_id, text, headers=ME, **timing):
    response = client.post(
        f"/v1/vivas/{viva_id}/answer",
        json={"text": text, "timing": timing or None},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _last(state, role="examiner"):
    return [t for t in state["turns"] if t["role"] == role][-1]


# ── Scope ───────────────────────────────────────────────────────────────────


def test_a_course_with_nothing_to_read_cannot_be_vivaed_and_says_why(client, model):
    response = _start(client)
    assert response.status_code == 422
    assert "nothing here to be examined on" in response.json()["detail"]


def test_a_scan_is_left_out_and_named(client, model):
    """EC-20.5, Trap 7: the viva says it cannot question on a scan."""
    _upload(client, data=b"\x89PNG\r\n\x1a\n" + b"\0" * 64, name="scan.png")
    _upload(client)
    scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
    assert scope["ready"] and [m["title"] for m in scope["materials"]] == ["lab6"]
    assert scope["excluded"][0]["title"] == "scan" and "scan" in scope["excluded"][0]["why"]
    assert scope["units"] == ["Lab 6"]


def test_someone_elses_private_material_is_not_in_my_scope(client, model):
    """AC-20.3 holds in the viva too: a private upload is its owner's alone."""
    _upload(client, headers=SOMEONE_ELSE)
    assert client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()["ready"] is False
    assert _start(client).status_code == 422


# ── The flow ────────────────────────────────────────────────────────────────


def test_a_viva_opens_with_a_greeting_and_an_unmarked_warm_up(client, model):
    _upload(client)
    state = _start(client).json()
    kinds = [t["kind"] for t in state["turns"]]
    assert kinds == ["greeting", "warmup"]
    assert "aim of Lab 6" in state["turns"][1]["text"], "a lab is asked its aim first"
    assert state["open"] == {
        "item": 0,
        "kind": "warmup",
        "stage": "asked",
        "hint_available": False,
        "answer_length": None,
    }
    # While the student answers, the first pages were banked.
    assert any(c["job"] == "viva_bank" for c in model.calls)
    state = _say(client, state["id"], "To compare FIFO and LRU page replacement.")
    assert [t["kind"] for t in state["turns"]][-2:] == ["ack", "question"]
    assert not [c for c in model.calls if c["job"] == "viva_marking"], "the warm-up is not marked"


def test_a_correct_answer_moves_on(client, model):
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing page replacement algorithms.")
    state = _say(client, state["id"], "A page is evicted when memory is full.")
    assert _last(state)["kind"] == "question" and state["open"]["item"] == 2
    answered = [t for t in state["turns"] if t["item"] == 1 and t["role"] == "student"][0]
    assert answered["verdict"] == "correct"


def test_a_partial_answer_gets_a_follow_up_that_does_not_give_it_away(client, model):
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    state = _say(client, state["id"], "Some page gets evicted.")
    follow = _last(state)
    assert follow["kind"] == "follow_up"
    assert "when does it happen?" in follow["text"].lower()
    assert "memory is full" not in follow["text"]
    state = _say(client, state["id"], "When memory is full.")
    assert _last(state)["kind"] == "question", "reached after the follow-up: moves on"


def test_a_blank_gets_a_hint_then_is_taught_with_the_page(client, model):
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    state = _say(client, state["id"], "I don't know.")
    assert _last(state)["kind"] == "hint"
    assert "no free frame" in _last(state)["text"]
    state = _say(client, state["id"], "Sorry, no idea.")
    teach = [t for t in state["turns"] if t["kind"] == "teach"][0]
    assert "the page is evicted" in teach["text"].lower() and "page 1 of lab6" in teach["text"]
    assert teach["cite"]["page"] == 1 and teach["cite"]["quote"]


def test_a_wrong_answer_gets_a_hint_not_the_answer(client, model):
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    state = _say(client, state["id"], "When memory is full it never evicts anything.")
    said = _last(state)["text"].lower()
    assert _last(state)["kind"] == "hint"
    assert "not quite" in said or "not right" in said
    assert "the page is evicted" not in said, "the hint does not give the answer"


def test_the_page_is_shown_after_the_answer_never_before(client, model):
    """Spec §2.3: the citation is in the state only once the question is closed."""
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    open_question = _last(state)
    assert open_question["kind"] == "question" and "cite" not in open_question
    state = _say(client, state["id"], "A page is evicted when memory is full.")
    closed = [t for t in state["turns"] if t["kind"] == "question" and t["item"] == 1][0]
    assert closed["cite"]["page"] >= 1


@pytest.mark.gate
def test_every_question_asked_cites_a_span_in_its_page(client, model, engine):
    """AC-20.2 [GATE], over a whole viva."""
    _upload(client)
    state = _start(client, questions=3).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    while state["status"] == "live":
        state = _say(client, state["id"], "A page is evicted when memory is full.")
    with Session(engine) as session:
        asked = [t for t in state["turns"] if t["kind"] == "question"]
        assert asked
        for turn in asked:
            cite = turn["cite"]
            page = session.get(MaterialPage, (cite["material_id"], cite["page"]))
            assert page.text[cite["span_start"] : cite["span_end"]] == cite["quote"]


def test_a_hint_can_be_asked_for_once(client, model):
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    response = client.post(f"/v1/vivas/{state['id']}/hint", headers=ME)
    assert response.status_code == 200 and _last(response.json())["kind"] == "hint"
    assert response.json()["open"]["hint_available"] is False
    assert client.post(f"/v1/vivas/{state['id']}/hint", headers=ME).status_code == 409


def test_a_viva_ends_after_its_questions_and_takes_no_more_answers(client, model):
    _upload(client)
    state = _start(client, questions=3).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    for _ in range(3):
        state = _say(client, state["id"], "A page is evicted when memory is full.")
    assert state["status"] == "ended" and state["end_reason"] == "complete"
    assert _last(state)["kind"] == "close"
    response = client.post(f"/v1/vivas/{state['id']}/answer", json={"text": "more"}, headers=ME)
    assert response.status_code == 409


def test_with_no_model_the_viva_still_runs_on_questions_by_rule(client):
    llm.set_llm(StubLLM(available=False))
    try:
        _upload(client)
        state = _start(client).json()
        state = _say(client, state["id"], "Comparing algorithms.")
        question = _last(state)
        assert question["kind"] == "question"
        assert (
            "aim" in question["text"]
            or "result" in question["text"]
            or "What is" in question["text"]
        )
    finally:
        llm.set_llm(None)


def test_starting_a_viva_ends_the_one_left_open(client, model):
    _upload(client)
    first = _start(client).json()
    second = _start(client).json()
    assert client.get(f"/v1/vivas/{first['id']}", headers=ME).json()["end_reason"] == "replaced"
    assert second["status"] == "live"


def test_an_attempt_then_i_dont_know_keeps_the_attempt(client, model):
    """Live, 2026-10-28: a real attempt, then "I don't know", read as "didn't
    know" — hiding that they tried."""
    _upload(client)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    state = _say(client, state["id"], "Some page gets evicted.")  # partial -> follow-up
    state = _say(client, state["id"], "I don't know.")  # -> taught
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["items"][0]["status"] == "partial"
    assert report["items"][0]["help"] == ["follow_up", "taught"]
    listed = client.get("/v1/vivas", headers=ME).json()[0]
    assert listed["answered"] == 1 and listed["correct"] == 0


def test_no_write_is_held_while_the_model_is_asked(client, engine):
    """Live, 2026-10-28: the request wrote its turn, then waited on the model
    with SQLite's one write lock held; the bank filling pages in the
    background waited 30 s and failed, "database is locked". Here every model
    call tries a write of its own, with no patience, and must get one."""
    import sqlite3

    path = engine.url.database
    blocked: list[str] = []

    class Writes(StubLLM):
        def structured(self, **kw):
            try:
                conn = sqlite3.connect(path, timeout=0.2)
                conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('probe', 'x')")
                conn.commit()
                conn.close()
            except sqlite3.OperationalError as exc:
                blocked.append(f"{kw['job']}: {exc}")
            return super().structured(**kw)

    llm.set_llm(Writes())
    try:
        _upload(client)
        state = _start(client, questions=3).json()
        state = _say(client, state["id"], "Comparing algorithms.")
        while state["status"] == "live":
            state = _say(client, state["id"], "Some page gets evicted.")
    finally:
        llm.set_llm(None)
    assert blocked == []


# ── Who may see it ──────────────────────────────────────────────────────────


def test_a_viva_is_its_students_alone(client, model):
    _upload(client, visibility="platform")
    state = _start(client).json()
    for headers in (SOMEONE_ELSE, as_curator()):
        assert client.get(f"/v1/vivas/{state['id']}", headers=headers).status_code == 404
        assert client.get(f"/v1/vivas/{state['id']}/report", headers=headers).status_code == 404
        assert (
            client.post(
                f"/v1/vivas/{state['id']}/answer", json={"text": "x"}, headers=headers
            ).status_code
            == 404
        )
    assert client.post("/v1/vivas", json={"course_id": COURSE}).status_code == 401


# ── The report ──────────────────────────────────────────────────────────────


def test_the_report_says_what_was_known_and_what_to_reread_with_the_page(client, model):
    _upload(client)
    state = _start(client, questions=3).json()
    viva_id = state["id"]
    _say(client, viva_id, "Um, comparing, like, algorithms.", silence_ms=2500)
    _say(client, viva_id, "A page is evicted when memory is full.", silence_ms=1200)
    _say(client, viva_id, "I don't know.", silence_ms=9000)
    _say(client, viva_id, "No idea.")
    state = _say(client, viva_id, "Some page gets evicted.")
    report = client.get(f"/v1/vivas/{viva_id}/report", headers=ME).json()

    statuses = [i["status"] for i in report["items"]]
    assert statuses[:2] == ["correct", "blank"]
    assert report["knew"] == [1]
    blank = report["items"][1]
    assert blank["help"] == ["hint", "taught"] and blank["missing"]
    reread = report["reread"]
    assert reread and reread[0]["page"] == blank["cite"]["page"] and reread[0]["quotes"]
    assert 2 in [i for r in reread for i in r["items"]]
    sounded = report["sounded"]
    assert sounded["fillers"] == 2 and sounded["long_silences"] == 1
    assert report["viva"]["scope"] == "Lab 6"


def test_the_report_says_the_marking_was_rough_only_when_it_was(client, model):
    """An "I don't know" is recognised by rule; that is not the marking model
    being down (live: the report said it was)."""
    _upload(client)
    state = _start(client).json()
    _say(client, state["id"], "Comparing algorithms.")
    _say(client, state["id"], "I don't know.")
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["marked_by_rules"] is False

    llm.set_llm(StubLLM(fail={"viva_marking"}))
    _say(client, state["id"], "Some page gets evicted.")
    report = client.get(f"/v1/vivas/{state['id']}/report", headers=ME).json()
    assert report["marked_by_rules"] is True


def test_my_vivas_are_listed_newest_first(client, model):
    _upload(client)
    first = _start(client).json()
    client.post(f"/v1/vivas/{first['id']}/end", headers=ME)
    second = _start(client).json()
    listed = client.get("/v1/vivas", headers=ME).json()
    assert [v["id"] for v in listed] == [second["id"], first["id"]]
    assert client.get("/v1/vivas", headers=SOMEONE_ELSE).json() == []


# ── The bank, reviewable (FR-20.14) ─────────────────────────────────────────


def test_the_bank_is_readable_with_the_material_and_reviewable_by_the_placement_cell(
    client, model, engine
):
    material = _upload(client, visibility="platform")
    _start(client)
    bank = client.get(f"/v1/vivas/bank/{material['id']}", headers=ME).json()
    assert bank["questions"] and all(q["quote"] for q in bank["questions"])
    question = bank["questions"][0]["id"]
    assert (
        client.post(
            f"/v1/vivas/bank/questions/{question}", json={"status": "retired"}, headers=ME
        ).status_code
        == 403
    )
    done = client.post(
        f"/v1/vivas/bank/questions/{question}", json={"status": "retired"}, headers=as_curator()
    )
    assert done.status_code == 200
    with Session(engine) as session:
        assert (
            session.exec(select(Question).where(Question.id == question)).one().status == "retired"
        )
    # Gone from the list, and back with `retired` — so a retirement can be undone.
    after = client.get(f"/v1/vivas/bank/{material['id']}", headers=as_curator()).json()
    assert question not in [q["id"] for q in after["questions"]]
    every = client.get(
        f"/v1/vivas/bank/{material['id']}", params={"retired": True}, headers=as_curator()
    ).json()
    assert {q["id"]: q["status"] for q in every["questions"]}[question] == "retired"
    assert all(q["current"] for q in every["questions"])
    assert every["pages_banked"] == 3 and every["skipped"] == []


@pytest.mark.parametrize(
    ("lead", "question", "said"),
    [
        ("Now, ", "Why does FIFO suffer?", "Now, why does FIFO suffer?"),
        ("Now, ", "LRU replaces which page?", "Now, LRU replaces which page?"),
        ("Now, ", "Belady's anomaly is what?", "Now, Belady's anomaly is what?"),
        ("Next: ", "Why does FIFO suffer?", "Next: Why does FIFO suffer?"),
    ],
)
def test_a_connector_runs_into_the_question(lead, question, said):
    """Live: "Now, Why does FIFO…"."""
    assert viva._connect(lead, question) == said


def test_short_and_long_questions_take_turns_starting_short(client, engine):
    """A viva asks a quick fact, then "explain…", then a quick one again."""

    class Mixed(StubLLM):
        def structured(self, **kw):
            result = super().structured(**kw)
            if kw["job"] == "viva_bank" and result.ok:
                # A long and a short question on every page of the part.
                mixed = []
                for long_one in result.data["questions"][:-1]:
                    short_one = {
                        **long_one,
                        "question": f"Name one thing from this: {long_one['question'][-30:]}",
                        "answer_points": long_one["answer_points"][:1],
                    }
                    mixed += [long_one, short_one]
                result.data["questions"] = mixed
            return result

    llm.set_llm(Mixed())
    try:
        _upload(client)
        state = _start(client, questions=4).json()
        state = _say(client, state["id"], "Comparing algorithms.")
        lengths = []
        while state["status"] == "live" and state["open"]:
            lengths.append(state["open"]["answer_length"])
            state = _say(client, state["id"], "A page is evicted when memory is full.")
    finally:
        llm.set_llm(None)
    assert lengths[0] == "short"
    assert all(a != b for a, b in zip(lengths, lengths[1:], strict=False)), lengths


def test_a_page_banked_under_an_older_prompt_is_banked_again_before_it_is_asked(
    client, model, engine, monkeypatch
):
    """Live, 2026-10-28: a lab banked under the first prompt kept serving its
    old questions — two-in-one ones the checks now refuse — because a banked
    page counted as done whatever it was banked under."""
    from backend_M20_Course_Viva import bank as bank_module
    from backend_M20_Course_Viva.models import BankPage

    _upload(client)
    first = _start(client).json()
    client.post(f"/v1/vivas/{first['id']}/end", headers=ME)
    with Session(engine) as session:
        for row in session.exec(select(BankPage)).all():
            row.prompt_version = "bank-0"
            session.add(row)
        for q in session.exec(select(Question)).all():
            q.prompt_version = "bank-0"
            session.add(q)
        session.commit()
    # With no background banking ahead of it, the choice itself must see the
    # page is out of date (each path is guarded on its own).
    monkeypatch.setattr(viva, "prefetch", lambda *a, **k: 0)
    state = _start(client).json()
    state = _say(client, state["id"], "Comparing algorithms.")
    asked = [t for t in state["turns"] if t["kind"] == "question"][-1]
    with Session(engine) as session:
        question = session.exec(
            select(Question).where(
                Question.status.in_(("draft", "reviewed")), Question.text == asked["text"]
            )
        ).first()
        assert question is not None and question.prompt_version == bank_module.PROMPT_VERSION


def test_each_examiner_is_a_persona_the_voice_engine_casts():
    """The room speaks in M11's voice for them and shows their face: an
    examiner M11 does not know would be a voice nobody cast."""
    for examiner in viva.EXAMINERS:
        assert examiner["voice_id"].startswith(("indictts-", "chatterbox-"))
        assert examiner["title"] and examiner["name"]


def test_the_examiner_is_one_of_the_panel_and_stays_for_the_viva(client, model):
    _upload(client)
    state = _start(client).json()
    assert state["examiner"]["name"] in [e["name"] for e in viva.EXAMINERS]
    assert state["examiner"]["name"] in state["turns"][0]["text"]


def test_the_four_examiners_take_turns_and_the_start_panel_knows_who_is_next(client, model):
    _upload(client)
    seen = []
    for _ in range(len(viva.EXAMINERS)):
        scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
        state = _start(client).json()
        assert state["examiner"] == scope["examiner"], "the panel showed who examines"
        seen.append(state["examiner"]["id"])
    assert sorted(seen) == sorted(e["id"] for e in viva.EXAMINERS)


def test_the_opening_s_fixed_words_are_said_as_the_start_panel_made_them(client, model):
    """The start panel has M11 make `say_first` ahead; the room then says the
    same sentences, so they are waiting in M11's cache."""
    _upload(client)
    scope = client.get(f"/v1/vivas/scope/{COURSE}", headers=ME).json()
    state = _start(client).json()
    opening = " ".join(t["text"] for t in state["turns"])
    made = scope["say_first"]
    assert made[0] == f"Hello, I'm {state['examiner']['name']}."
    for line in made[:3]:
        assert line in opening
    after = _say(client, state["id"], "To compare FIFO and LRU page replacement.")
    assert _last(after)["kind"] == "question"
    ack = next(t["text"] for t in after["turns"] if t["kind"] == "ack")
    assert ack in made


def test_a_refused_start_leaves_the_open_viva_open(client, model):
    _upload(client)
    open_one = _start(client).json()
    refused = _start(client, material_ids=["no-such-material"])
    assert refused.status_code == 404
    again = client.get(f"/v1/vivas/{open_one['id']}", headers=ME).json()
    assert again["status"] == "live", "only a viva that starts replaces the open one"


def test_signing_in_is_asked_for_the_viva_not_for_adding_material(client, model):
    response = client.get("/v1/vivas")
    assert response.status_code == 401 and response.json()["detail"] == "Sign in to take a viva."


def test_a_draft_the_bank_replaced_is_superseded_and_not_in_the_review_list(client, model, engine):
    """"Retired" is what a person did; a curator's list of what they retired
    had every draft a re-bank replaced in it (live, 2026-10-28)."""
    from backend_M20_Course_Viva import bank as bank_module

    material = _upload(client, visibility="platform")
    _start(client)
    with Session(engine) as session:
        for row in session.exec(select(bank_module.BankPage)).all():
            row.prompt_version = "bank-0"
            session.add(row)
        session.commit()
        bank_module.ensure(session, material["id"], 1, llm=model)
        statuses = {q.status for q in session.exec(select(Question)).all()}
    assert "superseded" in statuses and "retired" not in statuses
    every = client.get(
        f"/v1/vivas/bank/{material['id']}", params={"retired": True}, headers=as_curator()
    ).json()
    assert {q["status"] for q in every["questions"]} == {"draft"}
