# M20 — Course Viva

> **The course library, and (next) a viva on it.** Every B.Tech and AI course at Amrita's five campuses, organised the way a student finds it, with the material to prepare its viva.
>
> Spec: [plan_in_depth/M20_Course_Viva.md](plan_in_depth/M20_Course_Viva.md) · TODO: [M20_Course_Viva_TODO.md](plan_in_depth/M20_Course_Viva_TODO.md) · Ports: API `8120`, web `5220` ([PORTS.txt](PORTS.txt))

Lab exams, viva voce, end-semester orals: students asked for practice at *speaking* an answer about their own course. That is not a job interview, so it is not M06. A viva cannot exist without the material, so this module starts there:

```
Amrita University / <Campus> / <Branch> / Semester_1 … Semester_8 / <CODE - Title> / your files
                                        / Electives / <Basket> / <CODE - Title> /
```

Each campus lists only the branches it runs; the programme's own page on amrita.edu is what says so.

```bash
git clone https://github.com/MNEMOS-PREP/Course_Viva
cd Course_Viva/Backend
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[sync,dev]"
.venv/Scripts/python -m pytest          # 24 passed, no network, no API key
cd ../Frontend && npm install
cd .. && start_viva.bat                 # API on :8120, web on :5220/library
```

No key is needed: the library browses, imports and searches with nothing else running. The catalogue ships in `packages/catalogue/amrita.json` and is loaded at start.

---

## What is built (phases 0 and 1)

| | |
|---|---|
| **Catalogue** | `jobs.sync_catalogue` reads amrita.edu's curriculum page (Engineering › B.Tech, and Artificial Intelligence), each programme's page (which campuses run it), and the newest *Curriculum and Syllabus* PDF: semester tables, elective baskets, and each course's syllabus page. 20 programmes, 46 campus offerings, 2,001 courses. Every row keeps its source URL. |
| **Browse** | Campus → branch → Semester 1–8 + Electives → course, with the syllabus beside the material and a link to its page in the PDF. |
| **Material** | Upload a file (PDF, Word, PowerPoint, text, images) or a link, with kind and unit/lab. Text is extracted per page and indexed (SQLite FTS5); scans are kept as `no_text`. The same file twice in a course is one material. |
| **Who sees what** | Private (only you), or everyone on the platform. Shared with no stated permission → **held** until the placement cell approves. Whoever added a file, or a curator, can take it down, and it then leaves every view and search. |
| **Folder import** | Download the empty tree (or `jobs.folders scaffold <dir>`), drop files into course folders, pick the folder on the import page. A dry run places every file or says why not, before a byte is uploaded; re-running adds nothing new. |
| **Search, coverage** | Courses by code, title or syllabus, and the pages of material that mention your words. Coverage shows which courses still have nothing. |

**What is not built:** the viva itself (phase 2). Nothing on screen offers one, so nothing promises it.

**Parse quality** is measured in the TODO, not assumed. 85% of semesters were read; a semester the reader missed says so on its tab and links the PDF.

## Commands

```bash
# Re-sync the catalogue from amrita.edu (pages and PDFs are cached in Backend/.cache)
.venv/Scripts/python -m backend_M20_Course_Viva.jobs.sync_catalogue

# The empty folder tree, to fill
.venv/Scripts/python -m backend_M20_Course_Viva.jobs.folders scaffold "D:/Course Material"

# Import a filled tree from the command line (the web page does the same)
.venv/Scripts/python -m backend_M20_Course_Viva.jobs.folders import "D:/Course Material/Amrita University" --dry-run
```

PyMuPDF is pinned to **1.28.2**. 2.0 changes `find_tables`, and the reader stops finding rows (no error, just an empty curriculum). This matches M04's pin.

## Layout

```
Backend/backend_M20_Course_Viva/
  models.py        institution, campus, programme, offering, curriculum, course, material, page
  catalogue.py     load the synced JSON (upsert; material survives a re-sync)
  library.py       the read side: tree, campus, programme, course, search, coverage
  materials.py     add a file or link, hold, approve, take down
  extract.py       format from the bytes, text per page
  importer.py      scaffold, plan, import the folder tree
  router.py        /v1/library/*
  jobs/            sync_catalogue, curriculum_pdf (the PDF reader), folders
Frontend/frontend_M20_Course_Viva/src/
  routes.tsx       /library/<campus>/<branch>/<year>/<code>, the folder tree as a URL
packages/catalogue/amrita.json   the synced catalogue
```
