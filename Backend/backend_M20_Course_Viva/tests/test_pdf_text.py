"""What a real slide deck's PDF does to its text, and the bank and the viva
coping with it (live, 2026-10-28: a 59-page TD / Q-learning / SARSA deck)."""

from __future__ import annotations

import pytest

from backend_M20_Course_Viva import bank, marking, materials, viva

#: Page 12 of the deck, as PyMuPDF read it: the update rule in Unicode's
#: mathematical italic letters, its brackets lost.
EQUATION_PAGE = (
    "Mathematically, the update rule for value prediction is:\n"
    "\U0001d449 \U0001d446\U0001d461 \u2190 \U0001d449 \U0001d446\U0001d461 + \U0001d6fc "
    "\U0001d445\U0001d461+1 + \U0001d6fe\U0001d449 \U0001d446\U0001d461+1 \u2212 "
    "\U0001d449 \U0001d446\U0001d461\n"
    "Where:\n\u2022\U0001d449 \U0001d446\U0001d461  =current estimate of the remaining travel time"
)
JOURNEY = (
    "Rajesh is planning to travel to Jaipur from Delhi in his car. A quick check on Google Maps "
    "shows him an \nestimated 5 hour journey. Unfortunately, there is an unexpected delay due to "
    "a roadblock."
)


def test_an_equation_quoted_in_plain_letters_is_found_as_the_page_has_it():
    quote = "V(St) <- V(St) + alpha Rt+1 + γV(St+1) - V(St)"
    span = bank.locate(quote.replace("alpha", "α"), EQUATION_PAGE)
    assert span is not None
    assert EQUATION_PAGE[span[0] : span[1]].startswith("\U0001d449 \U0001d446\U0001d461")


def test_math_letters_are_the_letters_they_are():
    assert marking.tokens("𝑅𝑡+1") == ["rt", "1"]
    assert bank.words("𝛾𝑉") == ["γv"]
    # A point copied from the page, answered in plain letters.
    point = "𝛾𝑉𝑆𝑡 discounted"
    assert marking.reached_by_words(point, "γVSt discounted")


def test_a_quote_that_drifts_at_its_end_keeps_the_part_that_is_the_page():
    """The model copied most of a sentence, then paraphrased its tail. What is
    kept is the page's own text — never the model's words."""
    quote = "A quick check on Google Maps shows him an estimated 5 hour drive to the city"
    start, end = bank.locate(quote, JOURNEY)
    # Carried to the end of its sentence, not cut where the model's words left off.
    assert (
        JOURNEY[start:end]
        == "A quick check on Google Maps shows him an \nestimated 5 hour journey."
    )


def test_a_quote_mostly_not_on_the_page_is_still_refused():
    assert bank.locate("Rajesh drove a truck from Mumbai to Pune in the rain", JOURNEY) is None


def test_a_quote_never_starts_inside_a_word():
    """ "ajesh is…" is not a quote of "Rajesh is…": what is kept starts at a word."""
    start, end = bank.locate("ajesh is planning to travel to Jaipur", JOURNEY)
    assert JOURNEY[start:end] == "is planning to travel to Jaipur"


def test_a_word_broken_across_lines_is_still_the_word():
    page = "The page replace-\nment policy decides which frame is freed when memory is full."
    assert bank.locate("The page replacement policy decides which frame", page) is not None


@pytest.mark.parametrize(
    ("points", "said"),
    [
        (["Temporal Differencing"], "Temporal Differencing."),
        (["Richard Sutton", "1988"], "Richard Sutton and 1988."),
        (
            [
                "Continuing tasks do not have a clear episode end",
                "Therefore updates cannot be performed during the task",
            ],
            "Continuing tasks do not have a clear episode end. Therefore updates cannot be "
            "performed during the task.",
        ),
        (["it does not wait for the true outcome."], "It does not wait for the true outcome."),
    ],
)
def test_the_answer_is_said_in_sentences_that_keep_their_capitals(points, said):
    assert viva._join_points(points) == said


@pytest.mark.parametrize(
    ("filename", "title"),
    [
        ("TD slide- Qlearning SARSA (1).pdf", "TD slide- Qlearning SARSA"),
        ("lab_6_page_replacement.pptx", "lab 6 page replacement"),
        ("Unit 3 (2019).pdf", "Unit 3 (2019)"),
        ("notes", "notes"),
    ],
)
def test_a_file_name_becomes_a_title_an_examiner_can_say(filename, title):
    assert materials.title_of(filename) == title


def test_a_quote_with_a_gap_is_found_piece_by_piece_and_spans_the_gap():
    """Live: "So the prediction improves by: 20 minutes ... So the estimate…"."""
    quote = "A quick check on Google Maps ... there is an unexpected delay due to a roadblock"
    start, end = bank.locate(quote, JOURNEY)
    said = JOURNEY[start:end]
    assert said.startswith("A quick check on Google Maps") and said.endswith("due to a roadblock")
    assert "estimated 5 hour journey" in said, "the gap is the page's own text"


def test_a_gap_quote_out_of_order_keeps_only_its_longest_piece():
    quote = "an unexpected delay due to a roadblock ... A quick check"
    start, end = bank.locate(quote, JOURNEY)
    assert JOURNEY[start:end] == "an unexpected delay due to a roadblock"


def test_a_too_short_quote_says_so():
    raw = {"questions": [{"page": 1, "question": "What is the new journey estimate?",
                          "quote": "estimated 5 hour journey",
                          "answer_points": [{"point": "5 hours 30 minutes", "probe": "How long?"}],
                          "hint": "", "difficulty": 1}]}  # fmt: skip
    drafted = bank.check(raw, {1: JOURNEY}, "m1", None, "stub")
    assert drafted.questions == [] and drafted.dropped[0].startswith("quote too short")


@pytest.mark.parametrize(
    ("question", "points"),
    [
        ("How does the page describe the TD error when the roadblock appears?", True),
        ("What must be defined in the MDP design slide?", True),
        ("What elements should be shown in the ‘Demo So Far and Next Plan’ slide?", True),
        ("What happens when the window slides past the last acknowledged frame?", False),
        ("Why does the sender's window slide forward?", False),
    ],
)
def test_pointing_at_a_slide_is_told_from_a_window_that_slides(question, points):
    assert bool(bank._POINTS_AT_PAGE.search(question)) is points


@pytest.mark.parametrize(
    ("asked", "kept"),
    [
        (
            "Based on the slide, what does a positive TD error indicate?",
            "What does a positive TD error indicate?",
        ),
        (
            "List two advantages of TD methods over Monte Carlo as given.",
            "List two advantages of TD methods over Monte Carlo.",
        ),
    ],
)
def test_what_points_at_the_page_is_taken_out_cleanly(asked, kept):
    assert bank._as_question(asked) == kept


def test_a_page_that_is_not_course_content_is_said_so_not_forced(session):
    """Live: "What must be defined in the MDP design slide?" — an assignment's
    instructions, asked as if they were taught."""
    from .stubs import StubLLM, deck

    logistics = (
        "Assignment 2: submit the MDP design, the demo so far and the next plan by Friday. "
        "Marks are given for the design, the demo and the presentation of the plan."
    )

    class SaysLogistics(StubLLM):
        def structured(self, **kw):
            result = super().structured(**kw)
            if kw["job"] == "viva_bank":
                result.data["questions"] = [q for q in result.data["questions"] if q["page"] != 2]
                result.data["not_examinable"] = [
                    {"page": 2, "kind": "logistics"},
                    {"page": 1, "kind": "taught"},
                ]
            return result

    model = SaysLogistics()
    material = materials.add_file(
        session, course_id="btech-cse-2023:23CSE201", data=deck([JOURNEY, logistics]),
        filename="td.pptx", added_by="s", kind="slides", visibility="private",
    ).material  # fmt: skip
    bank.ensure(session, material.id, 1, llm=model)
    calls = [c["user"] for c in model.calls if c["job"] == "viva_bank"]
    assert all("[PAGE 2]" not in call for call in calls[1:]), "no retry for it"
    assert not bank.asked_from(session, [(material.id, 2)]), "no rule question either"
    row = session.get(bank.BankPage, (material.id, 2))
    assert row.reason == bank.NOT_EXAMINABLE["logistics"]
    assert bank.asked_from(session, [(material.id, 1)]), "an unknown kind skips nothing"


def _asked(question: str) -> list[str]:
    raw = {
        "questions": [
            {
                "page": 1,
                "question": question,
                "quote": "A quick check on Google Maps shows him an estimated 5 hour journey.",
                "answer_points": [{"point": "an estimated 5 hour journey", "probe": "How long?"}],
                "hint": "",
                "difficulty": 1,
            }
        ]
    }
    return [q.text for q in bank.check(raw, {1: JOURNEY}, "m1", None, "stub").questions]


def test_a_question_pointing_at_the_page_is_mended_when_it_can_be():
    assert _asked("What journey time is estimated in the example shown on this page?") == [
        "What journey time is estimated in the example?"
    ]


def test_a_question_that_still_points_at_the_page_is_not_asked():
    """Live: "What term does the slide use for the learning method…"."""
    assert _asked("What journey time does the slide give for Rajesh?") == []
    assert _asked("What journey time does Google Maps estimate for Rajesh?") != []


def test_a_decimal_point_does_not_end_a_sentence():
    """Live: "What can you tell me about EPISODE 2?" quoted "T[0] | A V=0."."""
    page = "EPISODE 2\nT[0] | A V=0.45 | B V=0.5 | C V=0.5 | T[1]\nStep 1: B to C, reward R=0."
    about = bank._about(page, "m1", 1)
    assert about and "V=0.45 | B V=0.5" in about[0].quote


@pytest.mark.parametrize(
    "point",
    ["α is 0.1", "δ = [R + γV(A)] − V(B)", "δ evaluates to -0.5", "V(A) becomes 0.45"],
)
def test_an_answer_point_in_numbers_and_symbols_is_checked_as_such(point):
    """A worked example's answers are numbers: every one was dropped."""
    page = (
        "Step 1: B -> A (Reward R=0)\nTD Error: δ = [R + γV(A)] − V(B)\n"
        "δ = [0 + 1 · 0] − 0.5 = −0.5\nUpdate V(A): V(A) ← 0.5 + 0.1 · (−0.5) = 0.45 with α = 0.1"
    )
    assert bank.grounded(point, page)


def test_numbers_not_on_the_page_do_not_ground_a_point():
    assert not bank.grounded("δ evaluates to 0.75", "TD Error: δ = 0.5 for this step")
