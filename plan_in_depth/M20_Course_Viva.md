# M20 — Course Viva: the Course Library and General Viva Practice

> **Master plan reference:** new module, added 2026-10-21 · **Phase:** 3 · **Owner:** E3 (library) + E2 (viva room) · **Depends on:** M04 (course concepts, evidence), M11 (voice), Platform_Core · **Feeds:** M04, M17, M19
> **Not an interview.** Every other practice round on this platform rehearses getting hired. This one rehearses being *examined on what you studied* — lab viva, viva voce, end-semester orals — and the speaking confidence those build.

---

## 1. In one paragraph

A library of every course a student actually takes, organised the way they think about it — **Amrita University → campus → branch → semester → course → material** — and a viva room that examines them on it. A student opens *Coimbatore → B.Tech CSE → Semester 4 → Operating Systems*, sees the syllabus, the lab manual, last year's papers and their notes, picks "Lab 6: Page replacement" and is questioned on it out loud the way an examiner would: *what is Belady's anomaly, why does FIFO show it, show me where your program counts faults*. Every question is drawn from — and cites — a page of that material, so nothing is asked that the course does not teach. The report says what they knew, what to reread (with the page), and how they *sounded*: pace, fillers, long silences, answers that never landed. The library is built first because a viva is only as good as its material, and because the structure — which branch runs at which campus, which courses each semester holds — is taken from the university's own published pages and curriculum PDFs, not typed by us.

---

## 2. Reverse-thinking: the user

### 2.1 The four people

1. **The student two days before a lab exam.** Knows roughly what the experiments were, has never had to *say* any of it aloud. Needs: the experiment's material in one place, and twenty minutes of being asked about it.
2. **The student who freezes in vivas.** Knows the answer in writing; goes blank when a faculty member looks at them. Needs: low-stakes repetitions until speaking an answer is normal, and evidence it is getting better (fewer fillers, shorter silences).
3. **The contributor** — a class representative, a TA, a faculty member. Has a folder of notes and lab manuals per course. Needs: to drop them in the right place once and see them used.
4. **The curator** (us, the placement cell). Needs: the whole university skeleton loaded in minutes, kept in step with the curriculum PDFs, and a way to see what is still empty.

### 2.2 The emotional arc

| Moment | What they feel | What the product does |
|---|---|---|
| Finding the course | "Is my branch even here?" | Their campus shows only the branches it runs; their semester shows the courses of their regulation year, by code |
| Before the viva | "I don't know what they'll ask" | Scope is visible: which documents and pages the questions will come from |
| First question | Nerves | A warm-up the examiner always asks (the aim of the experiment) |
| A blank | Panic | "Take a moment" → a hint from the page → if still blank, the answer, *taught*, with the page to reread |
| The report | "Did I do okay?" | What they knew, what to reread (page-cited), how they sounded — and the trend across vivas |

### 2.3 The screens

```
┌─ Library ───────────────────────────────────────────────────────────────────┐
│ Amrita University                                         [ Search all  ⌕ ] │
│  Amritapuri (11)   Coimbatore (17)   Bengaluru (9)   Chennai (8)   Amaravati │
│ ─ Coimbatore › B.Tech CSE (2023 curriculum) ─────────────────────────────── │
│  Semester  1  2  3  [4]  5  6  7  8                                        │
│   23CSE201  Operating Systems            4 cr   ▣ syllabus  ▣ 3 notes  ▣ lab │
│   23CSE202  Database Management Systems  4 cr   ▣ syllabus  — nothing yet —  │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 23CSE201 Operating Systems ───────────────────────────────────────────────┐
│ Syllabus · Notes · Lab manual · Question papers · References   [ + Add ]   │
│  Unit 1  Processes and threads ............ notes-u1.pdf (42 pp)           │
│  Lab 6   Page replacement algorithms ...... lab-manual.pdf pp 31–36       │
│ [ Start a viva on this course ]  [ …on Unit 3 ]  [ …on Lab 6 ]             │
└─────────────────────────────────────────────────────────────────────────────┘
```

The viva room is the platform's voice room (M11's turn-taking, the examiner's face and voice), with the material open beside it: the page a question came from is shown after the answer, never before.

---

## 3. Reverse-thinking: the developer

### 3.1 The traps

**Trap 1 — Copying the course five times.** Amrita's curricula are university-wide per regulation year: B.Tech CSE 2023 is the same course list at Amritapuri and at Chennai. Storing courses per campus means five copies, five sets of uploads, and four of them empty. *Counter: courses belong to a curriculum; a campus OFFERS a programme; material belongs to a course and is shared, with an optional campus tag for what really is local (one faculty member's notes).* The folder view the student sees is campus-first; the storage is not.

**Trap 2 — Typing the skeleton by hand.** Which branches each campus runs changes every admission cycle (2026: CSE at seven campuses, Aerospace at one). A hand-typed list is one cycle behind and silently wrong. *Counter: the catalogue is synced from the university's own pages — `amrita.edu/academics/curriculum/` for programmes, regulation years and curriculum PDFs; each programme page's "offered at the following campus" block for the campus matrix — with the source URL and fetch date stored on every row.*

**Trap 3 — One curriculum per branch.** A 2024 student and a 2019 student in "Semester 4 CSE" study different courses. *Counter: a curriculum is (programme, regulation year); a student's is the latest one at or before their batch year; the UI says which ("2023 curriculum").*

**Trap 4 — Questions the course does not teach.** A model asked to "viva a student on Operating Systems" will ask about whatever it likes. *Counter: every question is generated from — and stores — a span of a specific page of a specific document; a question without a resolvable span is never asked (the M09 rule, kept).*

**Trap 5 — Turning into an interview.** The interview engine (M06) is right there and tempting. A viva is not an interview: no "tell me about yourself", no hiring rubric, no company. *Counter: own question families (definition, explain-why, procedure, observation/result, application, numerical, compare) and an examiner persona; reuse M11's voice and M13's scoring style, not M06's plan.*

**Trap 6 — Material nobody may share.** Faculty notes and lab manuals are someone's work. *Counter: every upload records who added it and under what permission; visibility is private / my campus / everyone on the platform; nothing is ever public on the internet; a takedown removes it everywhere.*

**Trap 7 — Scanned PDFs.** Many lab manuals are photocopies. There is no OCR on this platform. *Counter: extraction reports `no_text`, the material is still stored and shown, and the viva says it cannot question on that file (OCR is an open decision).*

**Trap 8 — The model allowance.** Groq's free tier is 200K tokens a day per model (measured 2026-10-19). Generating questions per viva would spend it in a handful of sessions. *Counter: questions are generated once per page-chunk and cached as a reviewed bank; a viva draws from the bank and spends model calls only on follow-ups and marking.*

### 3.2 The non-obvious hard parts

1. **Curriculum PDFs vary by year.** 2010–2015 split curriculum and syllabus into two PDFs; 2019+ are one PDF with "Common Electives" separate; some links on the source page are wrong (2023 RAI lists the 2017 Mechanical curriculum under "&"). The parser handles the 2019+ layout (M04's reader, which already parses CSE 2023 and AIE 2022) and flags the rest for review rather than guessing.
2. **Course identity.** The same title recurs across programmes ("Engineering Mathematics"); the code is the identity (`23CSE201`), scoped by curriculum.
3. **Speaking measures need the audio timeline, not the text.** Pace and silences come from M11's turn timings; fillers from the transcript with its own word timings.

---

## 4. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-20.1 | Hierarchy: institution → campus → programme offered at campus → curriculum (regulation year) → semester → course → material | P0 |
| FR-20.2 | Catalogue synced from the university's published pages and curriculum PDFs, with source URL and fetch date on every row; re-runnable, idempotent | P0 |
| FR-20.3 | A campus shows only the programmes it offers; a programme shows its semesters and courses for the chosen regulation year | P0 |
| FR-20.4 | Course syllabus text (units) extracted from the curriculum PDF and shown as the course's first material | P0 |
| FR-20.5 | Upload material to a course: PDF, DOCX, PPTX, images, links; kind (syllabus, notes, slides, lab manual, question paper, reference, video link); unit or lab number | P0 |
| FR-20.6 | Bulk import from a folder tree that mirrors the hierarchy (`Amrita University/<Campus>/<Branch>/Semester_<n>/<Course>/…`), dry-run first, idempotent by content hash | P0 |
| FR-20.7 | Scaffold: generate that empty folder tree for every campus, branch, semester and course, so contributors only drop files | P0 |
| FR-20.8 | Text extraction per page (PDF/DOCX/PPTX) with page numbers; `no_text` reported for scans | P0 |
| FR-20.9 | Full-text search across all material, filterable by campus, branch, semester, course | P1 |
| FR-20.10 | Material is shared across campuses by default; a campus-specific tag where it is local | P0 |
| FR-20.11 | Visibility (private / campus / platform), provenance (who, when, permission) and takedown | P0 |
| FR-20.12 | Coverage view: which campuses, semesters and courses still have no material | P1 |
| FR-20.13 | Viva scope: whole course, units, labs, or chosen documents/pages | P0 |
| FR-20.14 | Question bank generated per page-chunk, each question citing its span; cached and reviewable | P0 |
| FR-20.15 | Viva session: examiner persona, spoken (M11) or typed, follow-ups on partial answers, hint then teach on a blank | P0 |
| FR-20.16 | Marking against the cited span: correct / partial / incorrect, with what was missing | P0 |
| FR-20.17 | Speaking measures: words per minute, fillers, silences before answering, answer length, unfinished answers | P0 |
| FR-20.18 | Report: knew / reread (page-cited) / how you sounded, and the trend over vivas | P0 |
| FR-20.19 | Lab viva mode: aim, principle, procedure, observations, result, precautions, sources of error | P1 |
| FR-20.20 | Results to the skill graph (M04) for courses with mapped concepts, behind consent | P1 |
| FR-20.21 | Platform sign-in and a "Library" and "Viva" entry in the shell | P0 |

---

## 5. Data contracts

```
Institution(id, name)
Campus(id, institution_id, name, source_url)
Programme(id, institution_id, degree, name, short, school, source_url)        # "btech-cse"
Offering(campus_id, programme_id, source_url, fetched_at)                     # who runs what where
Curriculum(id, programme_id, year, title, documents[], status)               # "btech-cse-2023"; status listed|parsed|reviewed
Course(id, curriculum_id, semester|null, code, title, credits, ltp, category, elective_basket|null, syllabus_text)
Material(id, course_id, campus_id|null, title, kind, unit|null, file|url, mime, bytes, sha256,
         pages, text_status, visibility, permission, added_by, status, created_at)
MaterialPage(material_id, page, text)                                         # + a full-text index
Question(id, material_id, page, span, family, text, answer_points[], difficulty, status)   # phase 2
Viva(id, student, scope, mode, started_at, ended_at); VivaTurn(...); VivaReport(...)      # phase 2
```

The course **code** is the identity inside a curriculum. A material's `sha256` makes import idempotent: the same file found under five campus folders is one material.

---

## 6. The pipelines

### 6.1 Catalogue sync (`jobs/sync_catalogue.py`)
1. `amrita.edu/academics/curriculum/` → for the Engineering › B.Tech and Artificial Intelligence sections: programmes, their regulation years and curriculum/syllabus/elective PDFs.
2. Each programme's page → the campuses it is offered at.
3. Each programme's latest curriculum PDF (2019+ layout) → semesters, courses, electives, and each course's syllabus text (M04's reader; one reader shared later through Platform_Core).
4. Every row keeps its source URL and fetch date; a PDF that fails to parse leaves the curriculum `listed`, never half-filled. One request a second; `robots.txt` allows `/program/` and the PDFs.

### 6.2 Folder import (`jobs/import_tree.py`) and scaffold (`jobs/scaffold.py`)
`<root>/Amrita University/<Campus>/<Branch short or name>/Semester_<n>/<CODE - Title>/<file>`. Branch and course are matched by code first, then by name; anything unmatched is listed in the dry run, never dropped. A file's kind comes from its folder or name (`lab`, `notes`, `slides`, `qp`/`pyq`, `syllabus`), else `notes`. Placed under a campus, it is tagged with that campus unless `--shared`.

### 6.3 Extraction
pypdf for PDF pages, python-docx, python-pptx; text per page; `no_text` when a page yields nothing (a scan).

### 6.4 Viva (phase 2)
Bank: per page-chunk, a model call drafts 3–6 questions in the families above, each with its span and answer points; a code check rejects any whose span is not in the page. Session: warm-up → scope-ordered questions → follow-up on partial → hint → teach. Marking: answer vs answer points, with the span. Speaking: from M11's turn timings and the transcript.

---

## 7. API surface (all under `/v1/library` and `/v1/vivas`; both nouns unused by other modules)

```
GET  /v1/library/tree                                  institution → campuses → programmes (counts)
GET  /v1/library/campuses/{campus}                     programmes offered there
GET  /v1/library/programmes/{programme}?campus=&year=  curricula and semesters with courses
GET  /v1/library/courses/{course_id}                   course, syllabus, materials (visible to the caller)
POST /v1/library/courses/{course_id}/materials         upload (multipart) or link
GET  /v1/library/materials/{id}/file | /pages          the file, the extracted pages
GET  /v1/library/search?q=&campus=&programme=&semester=
GET  /v1/library/coverage                              what is still empty
POST /v1/library/import  (curator)                     a folder tree as a zip; dry_run=true first
POST /v1/vivas …                                       phase 2
GET  /health   GET /v1/deps
```

---

## 8. UI specification

Library home (campus cards with branch counts) → campus (branches it runs) → programme (regulation year switch, semester tabs, course rows with material counts) → course (syllabus first, then materials grouped by kind, unit and lab; add material; start a viva on the course, a unit or a lab). Curator screens: import (folder upload with the dry-run report), coverage. Desktop first (1280–1440), the shell's tokens.

---

## 9. Edge cases

| EC | | Expected behaviour |
|---|---|---|
| EC-20.1 | A branch at one campus only (Aerospace: Coimbatore) | Shown only there |
| EC-20.2 | A curriculum PDF that will not parse | Curriculum stays `listed` with its PDFs linked; flagged for review |
| EC-20.3 | The source page links the wrong PDF (2023 RAI "&" → 2017 Mechanical) | Detected (title/programme mismatch), not imported, reported |
| EC-20.4 | The same file dropped under five campus folders | One material; five campus tags only if not `--shared` |
| EC-20.5 | A scanned lab manual | Stored and shown; `no_text`; the viva says it cannot question on it |
| EC-20.6 | A student between regulation years | Their batch year picks the curriculum; they can switch |
| EC-20.7 | An elective basket | Listed under its slot ("Professional Elective I") with the options |
| EC-20.8 | Material without permission | Visible to its uploader only until a curator approves |
| EC-20.9 | A takedown | Removed from every view, search and question bank |
| EC-20.10 | Duplicate upload with a new name | Recognised by hash; the existing material is shown |

---

## 10. Failure modes & fallbacks

amrita.edu unreachable → the last synced catalogue stands. A PDF the parser cannot read → `listed`, not guessed. Model allowance spent (phase 2) → the bank still serves cached questions; marking waits, and the student is told. M04 down → nothing is lost; results are not sent.

## 11. Performance & cost

Library pages from the database, no model calls. Sync: ~25 pages and ~40 PDFs, under ten minutes, run when the university publishes. Viva bank: one model call per page-chunk, once. A viva: follow-ups and marking only.

## 12. Test plan

Parser on CSE 2023 and AIE 2022 (known-good from M04) and one 2019 PDF; sync idempotency; folder import dry-run and dedupe; visibility; search; the API's shapes; the UI walked headless.

## 13. Metrics & acceptance gates

| ID | Metric | Target |
|---|---|---|
| AC-20.1 **[GATE]** | Every campus shows exactly the programmes its programme pages list | 100% on sync |
| AC-20.2 **[GATE]** | Every viva question cites a span that is in its page | 100% |
| AC-20.3 **[GATE]** | Nothing a student uploads is visible beyond its visibility setting | 100% |
| AC-20.4 | Courses parsed for the latest curriculum of every in-scope programme | ≥ 90% |
| AC-20.5 | Folder import re-run creates nothing new | 0 duplicates |
| AC-20.6 | A student's speaking measures improve over five vivas | reported |
| AC-20.7 | Curator loads a semester's folder in under five minutes | measured |

---

## 14. Build order

| Phase | Work | Done when |
|---|---|---|
| 0 | This spec, the TODO, the repo, the skeleton (ports 8120/5220) | the module starts and answers `/health` |
| 1 | Library: data model, catalogue sync for Engineering B.Tech + AI, folder scaffold and import, upload, extraction, search, browse UI | the five campuses, their branches, semesters and courses browse; a folder of material imports |
| 2 | Viva: question bank with spans, viva room (typed, then spoken), marking, report | a student is vivaed on a lab manual and gets a page-cited report |
| 3 | Speaking measures and trends; lab-viva mode | a student sees their fillers and silences fall |
| 4 | Platform: sign-in, shell entries, M04 evidence, curator review queue | a student signed in on :5173 opens their course and vivas |

## 15. Open decisions

1. **Scope beyond B.Tech and the AI school** (M.Tech, B.Sc., …): the model is degree-agnostic; the sync starts with B.Tech + AI as asked.
2. **Campuses beyond the five** (Nagercoil, Haridwar, Faridabad also run B.Tech): data-driven; enable when wanted.
3. **OCR for scanned manuals** — needs a model or a local engine; cost/quality decision.
4. **Who may upload** — students, or faculty and class representatives only?
5. **Pre-2019 curricula** (two-PDF layout): parse, or link only?
