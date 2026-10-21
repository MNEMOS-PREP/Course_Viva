"""The folder tree: scaffold, plan, import (FR-20.6, FR-20.7, AC-20.5)."""

from __future__ import annotations

from backend_M20_Course_Viva import importer, library
from backend_M20_Course_Viva.library import Viewer

ROOT = "Amrita University"
OS = f"{ROOT}/Coimbatore/CSE/Semester_4/23CSE201 - Operating Systems"


def test_the_scaffold_is_the_tree_the_importer_reads(session, tmp_path):
    counts = importer.scaffold(session, tmp_path)
    # Course FOLDERS: CSE's three under each of its two campuses, Aerospace's one.
    assert counts == {"campuses": 2, "branches": 4, "courses": 7}
    assert (tmp_path / OS).is_dir()
    assert (
        tmp_path / ROOT / "Coimbatore" / "CSE" / "Electives" / "Professional Elective I"
    ).is_dir()
    assert (tmp_path / ROOT / "Coimbatore" / "AE" / "Semester_1").is_dir()
    assert not (tmp_path / ROOT / "Amritapuri" / "AE").exists()  # not run there
    assert (tmp_path / ROOT / "README.txt").exists()
    # Every scaffolded course folder resolves back to its course.
    placement, reason = importer.locate(session, f"{OS}/notes.pdf")
    assert reason is None and placement.course_id == "btech-cse-2023:23CSE201"


def test_each_file_is_placed_or_told_why_not(session):
    plan = importer.plan(
        session,
        [
            f"{OS}/lab/Lab 6 page replacement.pdf",
            f"{OS}/PYQ 2024 end sem.pdf",
            f"{OS}/unit-3 notes.docx",
            f"{ROOT}/Coimbatore/CSE/Semester_4/Operating Systems/by-title.pdf",
            f"{ROOT}/Amritapuri/AE/Semester_1/19AEE101 - Engineering Mechanics/x.pdf",
            f"{ROOT}/Kochi/CSE/Semester_4/23CSE201/x.pdf",
            f"{OS}/README.txt",
        ],
    )
    placed = {p.path.rsplit("/", 1)[-1]: p for p in plan.placed}
    assert placed["Lab 6 page replacement.pdf"].kind == "lab_manual"
    assert placed["Lab 6 page replacement.pdf"].unit == "Lab 6"
    assert placed["PYQ 2024 end sem.pdf"].kind == "question_paper"
    assert placed["unit-3 notes.docx"].unit == "Unit 3"
    assert placed["by-title.pdf"].course_id == "btech-cse-2023:23CSE201"  # matched by title
    reasons = {p["path"].split("/")[1]: p["reason"] for p in plan.problems}
    assert "does not run" in reasons["Amritapuri"]
    assert "no campus folder" in reasons["Kochi"]
    assert len(plan.problems) == 2  # README.txt is skipped, not a problem


def test_importing_twice_adds_nothing_the_second_time(session):
    """AC-20.5, and the campus folder is remembered unless shared."""
    files = {f"{OS}/notes.docx": b"Paging divides memory into frames. " * 20}
    first = importer.run(session, files, "curator")
    second = importer.run(session, files, "curator")
    assert (first["added"], second["added"], second["already_there"]) == (1, 0, 1)
    shown = library.course(session, "btech-cse-2023:23CSE201", Viewer("x"))["materials"]
    assert shown[0]["campus_id"] == "coimbatore"
