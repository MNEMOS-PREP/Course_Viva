"""A small catalogue on a throwaway database and storage folder.

Two campuses, three programmes: CSE at both, Aerospace at Coimbatore only (the
one-campus branch of EC-20.1), and a programme with no parsed curriculum.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend_M20_Course_Viva import catalogue, config, db

CATALOGUE = {
    "institution": {"id": "amrita", "name": "Amrita Vishwa Vidyapeetham", "display": "Amrita University"},
    "campuses": [{"id": "amritapuri", "name": "Amritapuri"}, {"id": "coimbatore", "name": "Coimbatore"}],
    "programmes": [
        {
            "id": "btech-cse", "degree": "B.Tech", "name": "Computer Science and Engineering",
            "short": "CSE", "school": "Engineering", "source_url": "https://example/cse",
            "campuses": ["amritapuri", "coimbatore"], "also_at": ["Nagercoil"],
            "curricula": [
                {
                    "year": 2023, "status": "parsed",
                    "documents": [{"label": "Curriculum and Syllabus", "url": "https://example/cse-2023.pdf"}],
                    "semesters": [
                        {"number": 4, "slots": [], "courses": [
                            {"code": "23CSE201", "title": "Operating Systems", "category": "CSE",
                             "ltp": "3-0-3", "credits": "4",
                             "syllabus": "Unit 1 Processes and threads. Unit 2 Paging, page replacement.",
                             "syllabus_page": 41},
                            {"code": "23CSE202", "title": "Database Management Systems",
                             "category": "CSE", "ltp": "3-0-3", "credits": "4"},
                        ]},
                    ],
                    "electives": [{"name": "Professional Elective I", "courses": [
                        {"code": "23CSE331", "title": "Computer Vision", "credits": "3"}]}],
                },
                {"year": 2019, "status": "listed", "documents": []},
            ],
        },
        {
            "id": "btech-ae", "degree": "B.Tech", "name": "Aerospace Engineering", "short": "AE",
            "school": "Engineering", "campuses": ["coimbatore"], "also_at": [],
            "curricula": [{"year": 2019, "status": "parsed", "documents": [], "semesters": [
                {"number": 1, "slots": [], "courses": [
                    {"code": "19AEE101", "title": "Engineering Mechanics", "credits": "3"}]}]}],
        },
        {
            "id": "btech-qc", "degree": "B.Tech", "name": "CSE (Quantum Computing)", "short": "QC",
            "school": "Engineering", "campuses": ["amritapuri"], "also_at": [],
            "curricula": [{"year": 2026, "status": "listed", "documents": []}],
        },
    ],
    "fetched_at": "2026-10-21T00:00:00+00:00",
}  # fmt: skip


@pytest.fixture
def engine(tmp_path, monkeypatch):
    eng = db.make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    db.init(eng)
    monkeypatch.setattr(db, "engine", eng)
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "storage")
    # The app loads its catalogue file at start: make that the fixture's, not the real sync.
    held = tmp_path / "amrita.json"
    held.write_text(json.dumps(CATALOGUE), encoding="utf-8")
    monkeypatch.setattr(config, "CATALOGUE_FILE", held)
    with Session(eng) as session:
        catalogue.load(session, CATALOGUE)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine):
    from backend_M20_Course_Viva.app import app

    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[db.get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def as_student(subject: str = "4d0aa1c0-0000-4000-8000-000000000004") -> dict:
    return {"X-Candidate-Id": subject, "X-Role": "student"}


def as_curator() -> dict:
    return {"X-Candidate-Id": "curator-1", "X-Role": "placement_officer"}
