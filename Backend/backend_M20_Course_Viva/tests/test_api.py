"""The HTTP surface: who may do what, and the shapes the web app reads."""

from __future__ import annotations

from .conftest import as_curator, as_student

OS = "btech-cse-2023:23CSE201"


def test_the_tree_and_a_campus(client):
    tree = client.get("/v1/library/tree").json()
    assert tree["institution"]["display"] == "Amrita University"
    assert [(c["name"], c["programmes"]) for c in tree["campuses"]] == [
        ("Amritapuri", 2),
        ("Coimbatore", 2),
    ]
    campus = client.get("/v1/library/campuses/coimbatore").json()
    assert {p["short"] for p in campus["programmes"]} == {"CSE", "AE"}
    assert client.get("/v1/library/campuses/kochi").status_code == 404


def test_adding_material_needs_a_signed_in_person(client):
    files = {"file": ("os.txt", b"Paging and segmentation. " * 10, "text/plain")}
    assert client.post(f"/v1/library/courses/{OS}/materials", files=files).status_code == 401
    made = client.post(
        f"/v1/library/courses/{OS}/materials",
        files=files,
        data={"kind": "notes", "unit": "Unit 2"},
        headers=as_student(),
    )
    assert made.status_code == 201, made.text
    material = made.json()["material"]
    assert material["unit"] == "Unit 2" and material["text_status"] == "ok"
    assert material["visibility"] == "held"  # shared, but no permission stated
    assert client.get(f"/v1/library/materials/{material['id']}/file").status_code == 404  # held
    file = client.get(f"/v1/library/materials/{material['id']}/file", headers=as_student())
    assert file.status_code == 200 and file.content.startswith(b"Paging")
    pages = client.get(f"/v1/library/materials/{material['id']}/pages", headers=as_student()).json()
    assert pages["pages"][0]["page"] == 1


def test_only_its_owner_or_the_curator_takes_material_down(client):
    files = {"file": ("os.txt", b"Threads share an address space. " * 10, "text/plain")}
    made = client.post(
        f"/v1/library/courses/{OS}/materials", files=files, headers=as_student("alice")
    ).json()
    mid = made["material"]["id"]
    assert (
        client.delete(f"/v1/library/materials/{mid}", headers=as_student("bob")).status_code == 403
    )
    assert client.delete(f"/v1/library/materials/{mid}", headers=as_curator()).status_code == 200
    assert client.get(f"/v1/library/materials/{mid}/file").status_code == 404


def test_a_folder_import_is_the_curators_and_dry_runs_first(client):
    path = "Amrita University/Coimbatore/CSE/Semester_4/23CSE201 - Operating Systems/lab/lab 2.txt"
    files = [("files", (path, b"Experiment 2: fork and exec. " * 10, "text/plain"))]
    assert client.post("/v1/library/import", files=files, headers=as_student()).status_code == 403
    dry = client.post("/v1/library/import", files=files, headers=as_curator()).json()
    assert dry["dry_run"] and dry["would_add"][0]["course_id"] == OS
    assert dry["would_add"][0]["kind"] == "lab_manual"
    assert client.get(f"/v1/library/courses/{OS}").json()["materials"] == []  # nothing yet
    done = client.post("/v1/library/import?dry_run=false", files=files, headers=as_curator()).json()
    assert done["added"] == 1


def test_search_and_coverage_answer(client):
    assert client.get("/v1/library/search", params={"q": "operating"}).json()["courses"]
    rows = client.get("/v1/library/coverage").json()
    assert {r["campus"] for r in rows} == {"Amritapuri", "Coimbatore"}


def test_health_says_what_is_loaded(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["courses"] == 4


def test_only_a_curator_approves_a_held_upload(client):
    files = {"file": ("ch3.txt", b"Deadlock needs four conditions at once. " * 10, "text/plain")}
    made = client.post(
        f"/v1/library/courses/{OS}/materials", files=files, headers=as_student("alice")
    ).json()
    mid = made["material"]["id"]
    approve = f"/v1/library/materials/{mid}/approve"
    assert client.post(approve, headers=as_student("alice")).status_code == 403
    assert client.post(approve, headers=as_curator()).json()["material"]["visibility"] == "platform"
    shown = client.get(f"/v1/library/courses/{OS}", headers=as_student("bob")).json()
    assert [m["id"] for m in shown["materials"]] == [mid]


def test_the_folder_tree_downloads_as_a_zip(client):
    import io
    import zipfile

    body = client.get("/v1/library/folders.zip")
    assert body.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(body.content)).namelist()
    assert "Amrita University/README.txt" in names
    assert "Amrita University/Coimbatore/CSE/Semester_4/23CSE201 - Operating Systems/" in names
