"""The warm-up names what the pages teach, from their own words, and never
asks "what do these pages cover?" (the user, 2026-10-31)."""

from __future__ import annotations

from backend_M20_Course_Viva import topic

MONTE_CARLO = [
    "Monte Carlo methods learn from complete episodes of experience.",
    "Monte Carlo estimates a state's value by averaging the returns that followed it.",
    "Monte Carlo control improves the policy after every episode.",
    "Dynamic programming needs a model of the environment.",
]


def test_the_phrase_the_pages_keep_coming_back_to_is_their_subject():
    assert topic.phrase(MONTE_CARLO) == "Monte Carlo"


def test_the_words_that_only_organise_a_deck_are_not_a_subject():
    furniture = [
        f"Batch 4 — PPT, Slides 31–40. Summary questions. {line}" for line in MONTE_CARLO
    ]
    found = topic.phrase(furniture)
    assert found == "Monte Carlo"
    assert not {"batch", "slides", "summary", "questions"} & set(found.lower().split())


def test_a_heading_capital_is_not_part_of_the_name():
    pages = [
        "Backup diagrams show one update.",
        "Backup diagrams of Monte Carlo reach the end of the episode.",
        "Backup diagrams of TD stop after one step.",
    ]
    assert topic.phrase(pages) == "backup diagrams"


def test_nothing_that_stands_out_is_nothing_not_a_guess():
    assert topic.phrase(["Alpha beta gamma delta.", "Epsilon zeta theta kappa."]) is None
    assert topic.phrase([]) is None


def test_a_heading_of_the_notes_own_furniture_is_not_a_subject():
    for heading in ("Contents: all batches", "Reinforcement learning class test study notes", "Summary"):
        assert topic.labels_the_notes(heading), heading
    for heading in ("Bellman equation", "Page replacement", "Batch normalisation"):
        assert not topic.labels_the_notes(heading), heading
