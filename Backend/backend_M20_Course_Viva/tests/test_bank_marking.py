"""The question bank, marking and the speaking measures — the rules that
decide what a student is asked, and what their answer is said to be."""

from __future__ import annotations

import pytest
from sqlmodel import select

from backend_M20_Course_Viva import bank, marking, materials, speaking
from backend_M20_Course_Viva.models import BankPage, Question

from .stubs import INVENTED, SLIDES, StubLLM, deck

COURSE = "btech-cse-2023:23CSE201"
STUDENT = "student-a"


def _material(session, data: bytes | None = None, *, by: str = STUDENT, filename="lab6.pptx"):
    added = materials.add_file(
        session,
        course_id=COURSE,
        data=data or deck(),
        filename=filename,
        added_by=by,
        kind="lab_manual",
        unit="Lab 6",
        visibility="private",
    )
    return added.material


# ── Quotes resolve, or the question is not asked (AC-20.2) ──────────────────


def test_a_quote_is_found_across_case_punctuation_and_line_breaks():
    page = "FIFO replaces the page\nthat has been in memory the longest; LRU does not."
    span = bank.locate("fifo replaces the page that has been in memory", page)
    assert span is not None
    assert page[span[0] : span[1]].startswith("FIFO replaces")


def test_a_quote_not_on_the_page_is_not_found():
    assert bank.locate(INVENTED, SLIDES[0]) is None
    assert bank.locate("FIFO replaces", SLIDES[0]) is None, "too short to cite anything"


@pytest.mark.gate
def test_a_question_whose_quote_is_not_on_its_page_is_dropped():
    """AC-20.2 [GATE]: every viva question cites a span that is in its page."""
    raw = (
        StubLLM()
        .structured(job="viva_bank", system="", user=f"<<<PAGE\n{SLIDES[0]}\nPAGE", schema={})
        .data
    )
    drafted = bank.check(raw, SLIDES[0], "m1", 1, "stub")
    assert [q.family for q in drafted.questions] == ["explain"]
    assert any("quote not on the page" in d for d in drafted.dropped)
    for q in drafted.questions:
        assert SLIDES[0][q.span_start : q.span_end] == q.quote


def test_a_probe_that_gives_the_point_away_is_replaced():
    raw = {
        "questions": [
            {
                "family": "explain",
                "question": "Why does FIFO show Belady's anomaly?",
                "quote": "FIFO suffers from Belady's anomaly, while LRU does not.",
                "answer_points": [
                    {
                        "point": "FIFO suffers from Belady's anomaly",
                        "probe": "FIFO suffers from Belady's anomaly?",
                    }
                ],
                "hint": "Count the faults.",
                "difficulty": 2,
            }
        ]
    }
    drafted = bank.check(raw, SLIDES[0], "m1", 1, "stub")
    assert drafted.questions[0].answer_points[0]["probe"] == "Can you say more about that?"


def _one(question: str, quote: str, points: list[dict], hint: str = "Count the faults.") -> dict:
    return {
        "family": "explain", "question": question, "quote": quote,
        "answer_points": points, "hint": hint, "difficulty": 2,
    }  # fmt: skip


def test_what_points_at_the_page_is_taken_out():
    """Live, 2026-10-28: "Look at the first sentence of the page", "…based on
    this page" — the student cannot see the page during a viva."""
    raw = {
        "questions": [
            _one(
                "When would you prefer LRU over FIFO based on this page",
                "FIFO suffers from Belady's anomaly, while LRU does not.",
                [
                    {
                        "point": "LRU does not suffer from Belady's anomaly",
                        "probe": "Look at the last sentence.",
                    }
                ],
                hint="Look at the first sentence of the page.",
            )
        ]
    }
    q = bank.check(raw, SLIDES[0], "m1", 1, "stub").questions[0]
    assert q.text == "When would you prefer LRU over FIFO?"
    assert q.hint == "" and q.answer_points[0]["probe"] == "Can you say more about that?"


@pytest.mark.parametrize(
    ("hint", "points_at_page"),
    [
        # Live, 2026-10-28, from gpt-oss-120b:
        ("Check the line that begins with 'Result'.", True),
        ("Look at the opening line that begins with 'Aim'.", True),
        ("Think about the phrase describing the page's usage history.", True),
        ("Look at the two algorithms named in the statement.", True),
        ("The result sentence directly compares the two algorithms.", True),
        ("Look at the contrasting statements about the two algorithms.", True),
        ("Look at the result statement concerning the two algorithms.", True),
        ("Look at the mechanisms mentioned for tracking usage.", True),
        ("List the three actions separated by commas in the procedure line.", True),
        # The subject, in an OS or a programming course:
        ("Think of the page that came in earliest.", False),
        ("What does the if statement check?", False),
        ("Trace the line of code that increments the counter.", False),
    ],
)
def test_a_hint_about_where_it_is_written_is_told_apart_from_the_subject(hint, points_at_page):
    assert bool(bank._POINTS_AT_PAGE.search(hint)) is points_at_page


def test_a_dropped_hint_is_replaced_by_a_probe_that_does_not_give_the_answer():
    raw = {
        "questions": [
            _one(
                "How does FIFO choose the page to replace?",
                "FIFO replaces the page that has been in memory the longest.",
                [
                    {
                        "point": "replaces the page in memory the longest",
                        "probe": "Think about arrival order.",
                    }
                ],
                hint="Check the line that begins with 'FIFO'.",
            )
        ]
    }
    assert (
        bank.check(raw, SLIDES[0], "m1", 1, "stub").questions[0].hint
        == "Think about arrival order."
    )


def test_a_question_that_cites_the_notes_loses_the_citation():
    """Live, 2026-10-28: "When is a page evicted according to the note?"."""
    assert bank._as_question("When is a page evicted according to the note?") == (
        "When is a page evicted?"
    )


def test_page_as_the_subject_of_the_course_is_kept():
    """In an Operating Systems course "page" is the topic, not the handout."""
    raw = {
        "questions": [
            _one(
                "What is stored in the page table?",
                "FIFO replaces the page that has been in memory the longest.",
                [
                    {
                        "point": "replaces the page in memory the longest",
                        "probe": "Which page goes first?",
                    }
                ],
                hint="Think of the page that came in earliest.",
            )
        ]
    }
    q = bank.check(raw, SLIDES[0], "m1", 1, "stub").questions[0]
    assert q.text == "What is stored in the page table?"
    assert q.hint == "Think of the page that came in earliest."
    assert q.answer_points[0]["probe"] == "Which page goes first?"


def test_a_point_the_page_does_not_make_is_dropped():
    """Live: "LRU stands for Least Recently Used", asked of a page that never says it."""
    raw = {
        "questions": [
            _one(
                "What does FIFO do?",
                "FIFO replaces the page that has been in memory the longest.",
                [
                    {
                        "point": "replaces the page in memory the longest",
                        "probe": "Which page goes?",
                    },
                    {
                        "point": "In systems where predictable latency is critical",
                        "probe": "Where?",
                    },
                ],
            )
        ]
    }
    drafted = bank.check(raw, SLIDES[0], "m1", 1, "stub")
    assert [p["point"] for p in drafted.questions[0].answer_points] == [
        "replaces the page in memory the longest"
    ]
    assert any("point not on the page" in d for d in drafted.dropped)


def test_what_an_acronym_stands_for_must_be_on_the_page_whole():
    """Live, 2026-10-28: "What does LRU stand for?" asked of a page that never
    expands it — "LRU", "recently" and "used" are on the page, "least" is not."""
    raw = {
        "questions": [
            _one(
                "What does LRU stand for in page replacement?",
                "LRU replaces the page that has not been used for the longest time.",
                [{"point": "LRU means Least Recently Used", "probe": "The full form?"}],
            )
        ]
    }
    drafted = bank.check(raw, SLIDES[1], "m1", 2, "stub")
    assert drafted.questions == []
    # A paraphrase of what the page does say still counts.
    assert bank.grounded("It replaces the page not used for the longest time", SLIDES[1])


def test_one_point_is_a_short_answer_several_a_long_one():
    quote = "FIFO replaces the page that has been in memory the longest."
    raw = {
        "questions": [
            _one(
                "Which page does FIFO evict?",
                quote,
                [{"point": "the page in memory the longest", "probe": "Which?"}],
            ),
            _one(
                "Why does FIFO evict that page?",
                "FIFO suffers from Belady's anomaly, while LRU does not.",
                [
                    {"point": "FIFO suffers from Belady's anomaly", "probe": "What anomaly?"},
                    {"point": "LRU does not", "probe": "And LRU?"},
                ],
            ),
        ]
    }
    lengths = [q.answer_length for q in bank.check(raw, SLIDES[0], "m1", 1, "stub").questions]
    assert lengths == ["short", "long"]


@pytest.mark.parametrize(
    ("question", "kept"),
    [
        ("What does LRU stand for and how does it decide which page to replace?", False),
        ("Which algorithm suffers from Belady's anomaly, and which does not?", True),
        (
            "In the context of the operating system lab you completed this semester, could you please "
            "explain in detail every reason why first in first out replacement suffers from the anomaly?",
            False,
        ),
    ],
)
def test_a_question_is_crisp_and_asks_one_thing(question, kept):
    raw = {
        "questions": [
            _one(
                question,
                "FIFO suffers from Belady's anomaly, while LRU does not.",
                [{"point": "FIFO suffers from Belady's anomaly", "probe": "Which one?"}],
            )
        ]
    }
    assert bool(bank.check(raw, SLIDES[0], "m1", 1, "stub").questions) is kept


def test_a_database_from_before_short_answers_gains_the_column(tmp_path):
    """create_all makes missing tables, never missing columns."""
    import sqlite3

    from backend_M20_Course_Viva import db

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE question (id VARCHAR PRIMARY KEY, text VARCHAR)")
    conn.execute("INSERT INTO question (id, text) VALUES ('q1', 'old')")
    conn.commit()
    conn.close()
    db._added_columns(db.make_engine(f"sqlite:///{path.as_posix()}"))
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT answer_length FROM question").fetchone() == ("long",)
    conn.close()


def test_no_more_than_two_questions_on_one_sentence():
    quote = "FIFO suffers from Belady's anomaly, while LRU does not."
    point = [{"point": "FIFO suffers from Belady's anomaly", "probe": "Which one does?"}]
    raw = {"questions": [_one(f"Question {n} about the anomaly?", quote, point) for n in range(3)]}
    assert len(bank.check(raw, SLIDES[0], "m1", 1, "stub").questions) == 2


def test_a_question_keeps_its_own_full_stop():
    """Live: "Describe the FIFO page-replacement rule.?"."""
    raw = {
        "questions": [
            _one(
                "Describe the FIFO page replacement rule.",
                "FIFO replaces the page that has been in memory the longest.",
                [{"point": "replaces the page in memory the longest", "probe": "Which page?"}],
            )
        ]
    }
    assert bank.check(raw, SLIDES[0], "m1", 1, "stub").questions[0].text.endswith("rule.")


def test_questions_by_rule_come_from_definitions_and_lab_headings():
    by_rule = bank.by_rule(SLIDES[0] + "\n" + SLIDES[2], "m1", 1)
    texts = [q.text for q in by_rule]
    assert "What is the aim of this experiment?" in texts
    assert "What result does this experiment give?" in texts
    assert any(t.startswith("What is") and "anomaly" in t for t in texts)
    page = SLIDES[0] + "\n" + SLIDES[2]
    for q in by_rule:
        assert q.generated_by == bank.RULES
        assert page[q.span_start : q.span_end] == q.quote


# ── Banked once (Trap 8) ────────────────────────────────────────────────────


def test_a_page_is_banked_once_for_everyone(session):
    material = _material(session)
    llm = StubLLM()
    bank.ensure(session, material.id, 1, llm=llm)
    bank.ensure(session, material.id, 1, llm=llm)
    assert len([c for c in llm.calls if c["job"] == "viva_bank"]) == 1
    row = session.get(BankPage, (material.id, 1))
    assert row.status == "ready" and row.generated_by == "stub-bank" and row.questions == 1


def test_with_no_model_a_page_is_banked_by_rule_then_by_the_model_when_one_answers(session):
    material = _material(session)
    bank.ensure(session, material.id, 3, llm=StubLLM(available=False))
    row = session.get(BankPage, (material.id, 3))
    assert row.generated_by == bank.RULES and row.questions >= 1
    bank.ensure(session, material.id, 3, llm=StubLLM())
    session.refresh(row)
    assert row.generated_by == "stub-bank"
    live = bank.asked_from(session, [(material.id, 3)])
    assert live and all(q.generated_by == "stub-bank" for q in live), "rule questions retired"


def test_a_failed_model_call_falls_back_to_rules_and_says_why(session):
    material = _material(session)
    row = bank.ensure(session, material.id, 3, llm=StubLLM(fail={"viva_bank"}))
    assert row.generated_by == bank.RULES and row.reason == "scripted failure"


def test_taking_material_down_retires_its_questions(session):
    """EC-20.9: removed from every view, search AND question bank."""
    material = _material(session)
    bank.ensure(session, material.id, 1, llm=StubLLM())
    materials.take_down(session, material.id)
    live = session.exec(
        select(Question).where(Question.material_id == material.id, Question.status != "retired")
    ).all()
    assert live == []


# ── Marking (FR-20.16) ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "answer",
    ["I don't know", "sorry, I don't remember this one", "no idea", "Um, not sure.", "pass", "  "],
)
def test_a_give_up_is_blank(answer):
    assert marking.is_blank(answer)


@pytest.mark.parametrize(
    "answer",
    ["I'm not sure, but I think FIFO evicts the oldest page", "Not sure — maybe LRU?"],
)
def test_an_unsure_answer_is_still_an_answer(answer):
    assert not marking.is_blank(answer)


def _question() -> Question:
    return Question(
        material_id="m1", page=1, span_start=0, span_end=10, quote=SLIDES[0][:200],
        family="explain", text="What happens when memory is full?",
        answer_points=[{"point": "the page is evicted", "probe": "Which page goes?"},
                       {"point": "memory is full", "probe": "When?"}],
    )  # fmt: skip


def test_every_point_reached_is_correct_some_is_partial_none_is_missed():
    q, llm = _question(), StubLLM()
    assert marking.mark(q, "A page is evicted because memory is full.", llm=llm).status == "correct"
    partial = marking.mark(q, "Some page gets evicted.", llm=llm)
    assert partial.status == "partial" and partial.covered == [0]
    # Talking around it says nothing wrong: missed, not incorrect (live, 2026-10-28:
    # "It evicts some page I think" was called incorrect).
    assert marking.mark(q, "The CPU schedules a process.", llm=llm).status == "missed"


def test_a_follow_up_answer_adds_to_what_was_reached():
    q = _question()
    marked = marking.mark(q, "Because memory is full.", already=[0], llm=StubLLM())
    assert marked.status == "correct" and marked.covered == [0, 1]


def test_a_contradiction_needs_the_students_own_words():
    q = _question()
    wrong = marking.mark(q, "When memory is full it never evicts anything.", llm=StubLLM())
    assert wrong.status == "incorrect"
    assert wrong.wrong == {
        "said": "it never evicts",
        "why": "Pages are evicted when memory is full.",
    }


def test_a_point_counts_only_with_evidence_in_the_answer():
    class Invents(StubLLM):
        def structured(self, **kw):
            result = super().structured(**kw)
            if kw["job"] == "viva_marking":
                for p in result.data["points"]:
                    p.update(covered=True, evidence="the page is evicted to disk")
            return result

    marked = marking.mark(_question(), "Something about frames.", llm=Invents())
    assert marked.status == "missed" and marked.covered == []


def test_with_no_model_points_are_matched_by_their_words_and_labelled():
    marked = marking.mark(_question(), "The page is evicted.", llm=StubLLM(available=False))
    assert marked.status == "partial" and marked.marked_by == marking.RULES


# ── Speaking (FR-20.17) ─────────────────────────────────────────────────────


def test_fillers_are_counted_the_way_m06_counts_them():
    found = speaking.fillers_in("Um, so basically, like, FIFO evicts, you know, the oldest page.")
    assert found == {"um/uh": 1, "basically": 1, "like": 1, "you know": 1}


def test_an_answer_that_stops_mid_thought_is_unfinished():
    assert speaking.unfinished("FIFO evicts the page that")
    assert speaking.unfinished("it depends on the...")
    assert not speaking.unfinished("FIFO evicts the oldest page.")


def test_pace_is_measured_on_spoken_answers_only():
    spoken = speaking.measure("one two three four five six", {"spoken": True, "duration_ms": 3000})
    typed = speaking.measure("one two three four five six", {"spoken": False, "duration_ms": 3000})
    assert spoken["wpm"] == 120 and typed["wpm"] is None


def test_a_trend_needs_three_vivas_and_says_which_way():
    def s(rate, silence):
        return {"fillers_per_100": rate, "silence_ms_median": silence}

    assert speaking.trend([s(9, 4000), s(8, 3000)]) is None
    falling = speaking.trend([s(9, 6000), s(7, 5000), s(4, 2500), s(3, 2000)])
    assert falling["fillers"] == "better" and falling["silences"] == "better"
