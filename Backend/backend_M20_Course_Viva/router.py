"""M20's HTTP surface (spec §7). Every noun under /v1/library — unused by any
other module, so the platform shell's proxy routes it here unambiguously."""

from __future__ import annotations

from typing import Annotated

from ai_core.identity import Role, principal_from_headers
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select

from . import config, importer, library, materials, storage
from .db import get_session
from .library import Viewer
from .models import Material, MaterialPage

router = APIRouter(prefix="/v1/library", tags=["library"])
SessionDep = Annotated[Session, Depends(get_session)]
#: Who may import folders and take material down for everyone.
CURATORS = {Role.admin, Role.placement_officer}


def viewer_of(request: Request) -> Viewer:
    principal = principal_from_headers(dict(request.headers))
    if principal is None:
        return Viewer()
    return Viewer(subject=principal.subject, admin=principal.role in CURATORS)


def signed_in(request: Request) -> Viewer:
    viewer = viewer_of(request)
    if viewer.subject is None:
        raise HTTPException(status_code=401, detail="Sign in to add material.")
    return viewer


def curator(request: Request) -> Viewer:
    viewer = signed_in(request)
    if not viewer.admin:
        raise HTTPException(status_code=403, detail="Only the placement cell can do that.")
    return viewer


@router.get("/tree")
def tree(db: SessionDep) -> dict:
    return library.tree(db)


@router.get("/campuses/{campus_id}")
def campus(campus_id: str, db: SessionDep, request: Request) -> dict:
    found = library.campus(db, campus_id, viewer_of(request))
    if found is None:
        raise HTTPException(status_code=404, detail="No such campus.")
    return found


@router.get("/programmes/{programme_id}")
def programme(programme_id: str, db: SessionDep, request: Request, year: int | None = None) -> dict:
    found = library.programme(db, programme_id, viewer_of(request), year)
    if found is None:
        raise HTTPException(status_code=404, detail="No such programme.")
    return found


@router.get("/courses/{course_id}")
def course(course_id: str, db: SessionDep, request: Request) -> dict:
    found = library.course(db, course_id, viewer_of(request))
    if found is None:
        raise HTTPException(status_code=404, detail="No such course.")
    return found


@router.post("/courses/{course_id}/materials", status_code=201)
async def add_material(
    course_id: str,
    db: SessionDep,
    request: Request,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    title: str | None = Form(default=None),
    kind: str = Form(default="notes"),
    unit: str | None = Form(default=None),
    visibility: str = Form(default="platform"),
    permission: str | None = Form(default=None),
    campus_id: str | None = Form(default=None),
) -> dict:
    viewer = signed_in(request)
    try:
        if file is not None:
            data = await file.read(config.MAX_UPLOAD_BYTES + 1)
            if len(data) > config.MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="That file is too large.")
            added = materials.add_file(
                db, course_id=course_id, data=data, filename=file.filename or "file",
                added_by=viewer.subject, kind=kind, title=title, unit=unit,
                campus_id=campus_id, visibility=visibility, permission=permission,
                by_curator=viewer.admin,
            )  # fmt: skip
        elif url:
            added = materials.add_link(
                db, course_id=course_id, url=url, title=title or url, added_by=viewer.subject,
                kind=kind if kind != "notes" else "reference", unit=unit,
                campus_id=campus_id, visibility=visibility,
            )  # fmt: skip
        else:
            raise HTTPException(status_code=422, detail="Add a file or a link.")
    except materials.MaterialError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"created": added.created, "material": library._material_out(added.material)}


def _readable(db: Session, material_id: str, viewer: Viewer) -> Material:
    material = db.exec(
        select(Material).where(Material.id == material_id, library.visible(viewer))
    ).first()
    if material is None:
        raise HTTPException(status_code=404, detail="No such material.")
    return material


@router.get("/materials/{material_id}/file")
def material_file(material_id: str, db: SessionDep, request: Request) -> FileResponse:
    material = _readable(db, material_id, viewer_of(request))
    if not material.sha256:
        raise HTTPException(status_code=404, detail="This material is a link, not a file.")
    path = storage.path_for(material.sha256, material.filename or "")
    if not path.exists():
        raise HTTPException(status_code=410, detail="The file is missing from storage.")
    return FileResponse(
        path, media_type=material.mime or "application/octet-stream",
        filename=material.filename, content_disposition_type="inline",
    )  # fmt: skip


@router.get("/materials/{material_id}/pages")
def material_pages(material_id: str, db: SessionDep, request: Request) -> dict:
    material = _readable(db, material_id, viewer_of(request))
    pages = db.exec(
        select(MaterialPage)
        .where(MaterialPage.material_id == material.id)
        .order_by(MaterialPage.page)
    ).all()
    return {
        "material": library._material_out(material),
        "pages": [{"page": p.page, "text": p.text} for p in pages],
    }


@router.post("/materials/{material_id}/approve")
def approve(material_id: str, db: SessionDep, request: Request) -> dict:
    curator(request)
    material = materials.approve(db, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Nothing is waiting under that id.")
    return {"material": library._material_out(material)}


@router.delete("/materials/{material_id}")
def take_down(material_id: str, db: SessionDep, request: Request) -> dict:
    viewer = signed_in(request)
    material = db.get(Material, material_id)
    if material is None or material.status == "removed":
        raise HTTPException(status_code=404, detail="No such material.")
    if not viewer.admin and material.added_by != viewer.subject:
        raise HTTPException(status_code=403, detail="Only who added it, or the placement cell.")
    materials.take_down(db, material_id)
    return {"removed": material_id}


@router.get("/search")
def search(
    db: SessionDep,
    request: Request,
    q: str = Query(min_length=2),
    programme: str | None = None,
    semester: int | None = None,
) -> dict:
    return library.search(db, q, viewer_of(request), programme_id=programme, semester=semester)


@router.get("/coverage")
def coverage(db: SessionDep, request: Request) -> list[dict]:
    return library.coverage(db, viewer_of(request))


@router.get("/folders.zip")
def folders_zip(db: SessionDep) -> Response:
    """The empty folder tree, to fill and import back (FR-20.6)."""
    return Response(
        importer.scaffold_zip(db),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="Amrita University.zip"'},
    )


@router.post("/import")
async def import_folder(
    db: SessionDep,
    request: Request,
    files: list[UploadFile] = File(...),
    dry_run: bool = Query(default=True),
    shared: bool = Query(default=False),
) -> dict:
    """A browser folder upload: each file's name is its path inside the folder."""
    viewer = curator(request)
    if dry_run:
        found = importer.plan(db, [f.filename or "" for f in files])
        return {
            "dry_run": True,
            "would_add": [p.__dict__ for p in found.placed],
            "problems": found.problems,
        }
    payload = {}
    for upload in files:
        data = await upload.read(config.MAX_UPLOAD_BYTES + 1)
        if len(data) <= config.MAX_UPLOAD_BYTES:
            payload[upload.filename or ""] = data
    return {"dry_run": False, **importer.run(db, payload, viewer.subject, shared=shared)}
