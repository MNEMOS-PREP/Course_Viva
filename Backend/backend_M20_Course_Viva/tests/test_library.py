"""The library: the tree, campuses, programmes, courses, materials, search."""

from __future__ import annotations

import io

import docx
import pytest

from backend_M20_Course_Viva import catalogue, library, materials
from backend_M20_Course_Viva.extract import extract, sniff
from backend_M20_Course_Viva.library import Viewer

from .conftest import CATALOGUE

CSE_OS = "btech-cse-2023:23CSE201"
ALICE, BOB = Viewer("alice"), Viewer("bob")
CURATOR = Viewer("curator", admin=True)
OWN = "my own notes"


def _docx(*paragraphs: str) -> bytes:
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


NOTES = _docx(
    "Page replacement decides which page leaves memory when a frame is needed.",
    "Belady's anomaly: with FIFO, more frames can mean more page faults.",
)


def test_each_campus_shows_only_the_branches_it_runs(session):
    """EC-20.1 / AC-20.1: Aerospace is a Coimbatore programme only."""
    amritapuri = {p["id"] for p in library.campus(session, "amritapuri", ALICE)["programmes"]}
    coimbatore = {p["id"] for p in library.campus(session, "coimbatore", ALICE)["programmes"]}
    assert amritapuri == {"btech-cse", "btech-qc"}
    assert coimbatore == {"btech-cse", "btech-ae"}


def test_a_programme_lists_its_semesters_and_electives_for_its_latest_parsed_year(session):
    view = library.programme(session, "btech-cse", ALICE)
    assert view["curriculum"]["year"] == 2023  # the 2019 one is only listed
    assert [s["number"] for s in view["semesters"]] == [4]
    assert {c["code"] for c in view["semesters"][0]["courses"]} == {"23CSE201", "23CSE202"}
    assert view["electives"][0]["name"] == "Professional Elective I"
    assert [y["year"] for y in view["curricula"]] == [2023, 2019]


def test_a_course_carries_its_syllabus_and_the_page_it_is_on(session):
    view = library.course(session, CSE_OS, ALICE)
    assert "page replacement" in view["course"]["syllabus"]
    assert view["course"]["syllabus_page"] == 41


def test_reloading_the_catalogue_keeps_material_and_follows_the_campus_list(session):
    materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="os.docx", added_by="alice", permission=OWN
    )
    newer = {**CATALOGUE, "fetched_at": "2026-11-01T00:00:00+00:00"}
    newer["programmes"] = [dict(p) for p in CATALOGUE["programmes"]]
    newer["programmes"][0]["campuses"] = ["coimbatore"]  # the page stopped listing Amritapuri
    catalogue.load(session, newer)
    assert "btech-cse" not in {
        p["id"] for p in library.campus(session, "amritapuri", ALICE)["programmes"]
    }
    assert len(library.course(session, CSE_OS, ALICE)["materials"]) == 1


def test_the_same_file_twice_is_one_material(session):
    """EC-20.10, whatever it was called the second time: by its uploader, or
    by anyone once it is shared with everyone."""
    first = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="a.docx", added_by="alice", permission=OWN
    )
    again = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="renamed.docx", added_by="alice"
    )
    by_bob = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="b.docx", added_by="bob"
    )
    assert first.created and not again.created and not by_bob.created
    assert again.material.id == first.material.id == by_bob.material.id


@pytest.mark.gate
@pytest.mark.parametrize("visibility", ["private", "held"])
def test_someone_elses_unshared_copy_is_never_handed_to_the_next_uploader(session, visibility):
    """AC-20.3: Alice's private (or not yet approved) copy stays hers when Bob
    adds the same file — Bob gets a material of his own, not hers."""
    alice = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="mine.docx", added_by="alice",
        visibility="private" if visibility == "private" else "platform",
    )  # fmt: skip
    assert alice.material.visibility == visibility
    bob = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="bobs.docx", added_by="bob",
        visibility="private",
    )  # fmt: skip
    assert bob.created and bob.material.id != alice.material.id
    assert bob.material.added_by == "bob" and bob.material.title == "bobs"
    assert [m["id"] for m in library.course(session, CSE_OS, BOB)["materials"]] == [
        bob.material.id
    ]


def test_a_private_copy_its_owner_removed_stops_no_one_else(session):
    mine = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="mine.docx", added_by="alice",
        visibility="private",
    )  # fmt: skip
    materials.take_down(session, mine.material.id)
    assert materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="x.docx", added_by="bob", permission=OWN
    ).created
    with pytest.raises(materials.MaterialError, match="taken down"):
        materials.add_file(
            session, course_id=CSE_OS, data=NOTES, filename="again.docx", added_by="alice"
        )


@pytest.mark.gate
def test_private_material_is_seen_only_by_its_owner(session):
    """AC-20.3: in the course view, the counts and search alike — the placement
    cell included: private is its owner's alone."""
    materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="mine.docx", added_by="alice",
        visibility="private",
    )  # fmt: skip
    assert len(library.course(session, CSE_OS, ALICE)["materials"]) == 1
    assert library.course(session, CSE_OS, CURATOR)["materials"] == []
    assert library.course(session, CSE_OS, BOB)["materials"] == []
    assert library.course(session, CSE_OS, Viewer())["materials"] == []
    assert library.search(session, "Belady", BOB)["pages"] == []
    assert library.search(session, "Belady", CURATOR)["pages"] == []
    assert library.search(session, "Belady", ALICE)["pages"]


def test_a_filtered_search_finds_pages_past_the_ones_it_filters_out(session):
    """The filters are part of the query, not applied to its first page of hits."""
    for n in range(40):
        materials.add_file(
            session, course_id="btech-ae-2019:19AEE101",
            data=_docx(f"Belady's anomaly, note {n}: more frames, more page faults."),
            filename=f"ae{n}.docx",
            added_by="alice", permission=OWN,
        )  # fmt: skip
    materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="os.docx", added_by="alice", permission=OWN
    )
    found = library.search(session, "Belady", BOB, programme_id="btech-cse", limit=5)["pages"]
    assert [p["course_id"] for p in found] == [CSE_OS]
    assert len(library.search(session, "Belady", BOB, limit=5)["pages"]) == 5


def test_units_are_in_number_order(session):
    for unit in ("Unit 10", "Unit 2", None, "Unit 1"):
        materials.add_file(
            session, course_id=CSE_OS, data=_docx(f"notes for {unit}"), filename="u.docx",
            added_by="alice", unit=unit, permission=OWN,
        )  # fmt: skip
    units = [m["unit"] for m in library.course(session, CSE_OS, BOB)["materials"]]
    assert units == [None, "Unit 1", "Unit 2", "Unit 10"]


def test_a_material_table_made_before_owner_uniqueness_is_rebuilt_with_its_rows(tmp_path):
    from sqlalchemy import text

    from backend_M20_Course_Viva import db

    eng = db.make_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    db.init(eng)
    with eng.begin() as conn:  # the table as it was made until 2026-10-26
        conn.exec_driver_sql("DROP TABLE material")
        conn.exec_driver_sql(
            "CREATE TABLE material (id VARCHAR NOT NULL, course_id VARCHAR NOT NULL, "
            "campus_id VARCHAR, title VARCHAR NOT NULL, kind VARCHAR NOT NULL, unit VARCHAR, "
            "filename VARCHAR, url VARCHAR, mime VARCHAR, bytes INTEGER NOT NULL, "
            "sha256 VARCHAR, pages INTEGER NOT NULL, text_status VARCHAR NOT NULL, "
            "visibility VARCHAR NOT NULL, permission VARCHAR, added_by VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL, created_at DATETIME NOT NULL, PRIMARY KEY (id), "
            "CONSTRAINT uq_material_course_hash UNIQUE (course_id, sha256))"
        )
        conn.exec_driver_sql(
            "INSERT INTO material VALUES ('m1', 'c', NULL, 't', 'notes', NULL, 'f', NULL, NULL, "
            "1, 'h', 0, 'ok', 'private', NULL, 'alice', 'published', '2026-10-21 00:00:00')"
        )
    db.init(eng)
    with eng.connect() as conn:
        ddl = conn.execute(text("SELECT sql FROM sqlite_master WHERE name = 'material'")).scalar()
        assert "uq_material_course_hash_owner" in ddl
        assert conn.execute(text("SELECT id, added_by FROM material")).all() == [("m1", "alice")]
        indexes = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'material'")
        ).scalars().all()
        assert {"ix_material_sha256", "ix_material_course_id"} <= set(indexes)
    db.init(eng)  # and again: nothing left to do


def test_search_finds_the_page_and_the_course(session):
    materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="os.docx", added_by="alice", permission=OWN
    )
    found = library.search(session, "Belady anomaly", BOB)
    assert found["pages"][0]["course_id"] == CSE_OS and found["pages"][0]["page"] == 1
    assert "[" in found["pages"][0]["snippet"]
    hit = library.search(session, "operating", BOB)["courses"][0]
    assert hit["code"] == "23CSE201"
    assert hit["campuses"] == ["amritapuri", "coimbatore"]  # where the link can take you
    assert (hit["short"], hit["match"]) == ("CSE", "title")
    # Found by its syllabus only, and said so.
    assert library.search(session, "page replacement", BOB)["courses"][0]["match"] == "syllabus"


def test_a_take_down_removes_it_everywhere(session):
    """EC-20.9, and the same file cannot quietly come back."""
    added = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="os.docx", added_by="alice", permission=OWN
    )
    materials.take_down(session, added.material.id)
    assert library.course(session, CSE_OS, CURATOR)["materials"] == []
    assert library.search(session, "Belady", CURATOR)["pages"] == []
    with pytest.raises(materials.MaterialError, match="taken down"):
        materials.add_file(session, course_id=CSE_OS, data=NOTES, filename="x.docx", added_by="bob")


def test_a_link_is_material_too(session):
    added = materials.add_link(
        session, course_id=CSE_OS, url="https://nptel.ac.in/courses/106105214", title="NPTEL OS",
        added_by="alice", kind="video",
    )  # fmt: skip
    assert added.material.text_status == "link"
    with pytest.raises(materials.MaterialError):
        materials.add_link(session, course_id=CSE_OS, url="ftp://x", title="x", added_by="a")


def test_formats_are_read_from_the_bytes_not_the_name():
    assert sniff(NOTES, "renamed.pdf") == "docx"
    assert extract(NOTES, "x.docx").status == "ok"
    assert extract(b"\x89PNG\r\n\x1a\n" + b"0" * 50, "scan.png").status == "no_text"
    assert extract(b"just bytes", "mystery.bin").status == "failed"


def test_coverage_says_what_is_still_empty(session):
    materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="os.docx", added_by="alice", permission=OWN
    )
    rows = {(r["campus"], r["short"]): r for r in library.coverage(session, ALICE)}
    assert rows[("Coimbatore", "CSE")]["courses"] == 3
    assert rows[("Coimbatore", "CSE")]["with_material"] == 1
    assert rows[("Amritapuri", "QC")]["courses"] == 0  # no parsed curriculum yet


def test_shared_with_no_permission_waits_for_a_curator(session):
    """EC-20.8: its uploader and curators see it; everyone else once approved."""
    added = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="faculty.docx", added_by="alice"
    )
    assert added.material.visibility == "held"
    assert len(library.course(session, CSE_OS, ALICE)["materials"]) == 1
    assert library.course(session, CSE_OS, BOB)["materials"] == []
    assert library.search(session, "Belady", BOB)["pages"] == []
    assert materials.approve(session, added.material.id).visibility == "platform"
    assert len(library.course(session, CSE_OS, BOB)["materials"]) == 1
    assert materials.approve(session, added.material.id) is None  # nothing left to approve


def test_a_curators_upload_needs_no_permission_stated(session):
    added = materials.add_file(
        session, course_id=CSE_OS, data=NOTES, filename="lab.docx", added_by="curator",
        by_curator=True,
    )  # fmt: skip
    assert added.material.visibility == "platform"
