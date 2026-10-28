# M20 — TODO · Course Viva (Course Library + General Viva Practice)

> **Completion: 88%** — 17 of 21 functional requirements met, 3 partly (2026-10-28, evening: a long document ten pages at a time with no page lost, lab viva mode, the bank's review screen, and Library + Viva in the platform shell). Spec: [M20_Course_Viva.md](M20_Course_Viva.md).
>
> _Method: `(met + ½ × partial) ÷ total`, counted from the spec — the same measure as every other module._

Task list for taking **M20 — Course Viva** to 100% of [M20_Course_Viva.md](M20_Course_Viva.md).

> **This is the branch that holds the plan.** The `todo` branch carries the
> spec and this list and nothing else, so the module's own history stays
> about its code. Sync it here when something lands.

> **Read this first when starting a session on M20.** It is the running state of
> the module: what is done, what is next, and what is deliberately deferred.

- **Repo:** `Course_Viva` · **Ports:** API 8120, web 5220 (PORTS.txt: 8100 + 20, 5200 + 20) · **API nouns:** `/v1/library`, `/v1/vivas`

Legend: ✅ done · 🟡 partly done · ⬜ not started

---

### 2026-10-28 (evening) — long documents, lab vivas, the review screen, the shell

The user: "if a user uploads a long PDF, how do you chunk it so that no loss
happens? Give him 10 pages at a time; while he finishes one we prepare the
next", and "fix these all" (shell entries, review screen, lab mode, real
material, speed, the silent 3D-head fallback in other modules). Tried on the
user's 59-page TD / Q-learning / SARSA deck, live, against Groq.

- ✅ **Ten pages at a time (`bank.PART_PAGES`).** A part is banked in one call
  (59 calls for that deck before). Every page with ≥ 130 characters must get a
  question — a call of its own if the model skips it, then a rule question,
  then "what can you tell me about…" — so no page with text is lost. The scope
  lists each part (done / ready / pictures / titles); the start panel opens on
  the first part not done; while one part is answered the next is banked, and
  the close line, the room and the report offer "go on to pages 11 to 20" (a
  part of only pictures is passed over). The report says which pages the
  questions came from, which are titles, which are pictures.
- ✅ **Lab viva (FR-20.19).** `style: "lab"` walks the experiment in a lab
  examiner's order — principle, procedure, observations, result, precautions,
  sources of error — skipping a step the manual does not state, round again
  when there are more questions; the aim is the warm-up, and a banked aim
  question comes only when nothing else is left. New families aim / result /
  precaution / error; Procedure, Observations and Sources of error headings by
  rule. On by default on the start panel when the choice is a lab manual. The
  report names each question's step.
- ✅ **Review screen (FR-20.14):** `/library/questions/:material`, linked from
  each material for the placement cell — every question with its page, quote,
  points and their follow-ups, hint and author; mark reviewed, retire,
  restore. A draft the bank replaced is `superseded`, not `retired` (the list
  of what a person retired had 40 replaced drafts in it).
- ✅ **In the platform shell (FR-20.21):** "Viva practice" and "Course library"
  in Platform_Shell's menu (library under Browse for staff), the `library` and
  `vivas` nouns → 8120, M20 in module.json (start.bat starts it).
- ✅ **The opening, made ahead.** The four examiners take turns, so the start
  panel knows who is next and shows them; their fixed lines ("Hello, I'm Dr.
  Narayan.", "If you don't know something, just say so.", "Let's begin with an
  easy one.", the acknowledgements) are made by M11 while the student chooses —
  on the CPU the opening took ~20 s to say as it was made.
- **Found on the real deck and fixed, each with a test:** equations in
  Unicode's math letters ("𝑉 𝑆𝑡 ← 𝑉 𝑆𝑡 + 𝛼 𝑅𝑡+1", brackets lost) never matched
  a quote that wrote "V(St)" — quotes now match on letters and digits in
  order, math letters folded, and a quote with a "…" gap or a drifting tail
  keeps what is the page's own; one invented family label failed a whole call
  (HTTP 400, ten pages without questions) — labels are checked in code, not by
  the schema; a viva whose first page had nothing to ask, banked on demand,
  ended after the warm-up ("That's everything…") — every page then banked was
  passed over unread; a part that ran out of questions never offered the next;
  pages that are an assignment's instructions were asked about as if taught —
  the model now lists logistics / references / outline / thanks pages, which are
  kept with that reason; questions pointing at the slide ("How does the page
  describe…", "in the MDP design slide", "as given", "the two bullet points")
  are mended or dropped; ", what does…" after "Based on the slide" was cut;
  the teach line ran points together ("…episode end; and Therefore…"); a
  browser's "(1)" was read out in the title; a refused start ended the viva
  left open; title slides were called pictures.
- **Elsewhere:** M06's standalone app sent `/v1/voice` to M06 and never
  pre-bundled the 3D-head renderer — the same silent fallback; the platform
  shell found the renderer only when first asked for and reloaded the page
  mid-render (a blank first screen after a restart).
- **Tests:** 178 backend (132 → 178), lint clean; frontend typecheck and build
  clean; the start panel, room, report and review screen walked headless, in
  the standalone app and in the shell.

### 2026-10-26 — the library's privacy and search, fixed (`8b6725e`)

- ✅ **A private copy stays its owner's (AC-20.3).** A material was unique per
  course and file, so a second student adding the same file was handed the first
  one's private or held row — its title, file name and permission — and their
  own upload vanished. Unique per course, file and uploader now (SQLite tables
  made before are rebuilt at start, rows kept); one file shared with everyone is
  still one material (EC-20.10); a shared file taken down stays down for
  everyone (EC-20.9); a private copy its owner removed stops no one else.
- ✅ **Curators no longer see private material.** They see what is shared and
  what waits for them (`held`); "seen only by its owner and the curator" in the
  old gate test was the leak, not the rule.
- ✅ **Filtered search finds what matches:** visibility, programme and semester
  were applied after the query's LIMIT.
- ✅ A folder import says when a file is over the size limit (it was dropped
  without a word); units sort as numbers ("Unit 2" before "Unit 10").
- ⬜ **EC-20.4's "five campus tags"** is not built: the same file under five
  campus folders is one material carrying the first campus only. 31 tests.

## 0. Why this module, and what it is not

Students asked for **general viva practice** — lab exams, viva voce, end-semester
orals — to build the confidence of *speaking* an answer. That is not interview
practice: the shell's "practise a course" runs M06's job interview on a course's
concepts, which is the wrong examiner, the wrong questions and the wrong goal.
So M20 is its own module, and it starts with the thing a viva cannot exist
without: **the material, organised the way students find it** —
Amrita University → campus → branch → semester → course → material.

Scope of the first sync (the user's call, 2026-10-21): **Engineering (B.Tech)**
and the **School of Artificial Intelligence** programmes, at the five campuses
**Amritapuri, Coimbatore, Bengaluru, Chennai, Amaravati**.

## Where it stands (2026-10-28)

**Phases 0, 1 and 2 are built.** The library is loaded and browsable on :5220,
and a student can be vivaed on their own material: a course page offers
"Practise a viva" on everything there, one unit or lab, or one document,
answered by speaking or typing; the examiner is seen (a 3D head, or their
photograph) and heard (M11's voice); the report says what they knew, what to
reread (page-cited), and how they sounded.

**Spoken and seen (2026-10-28, the user: "spoken and visual vivas, just like a
real examiner, crisp questions covering long and short answers"):**

- **The examiners** are four of the platform's academic interviewers (Dr.
  Raghavan, Dr. Narayan, Professor Murthy, Dr. Deshpande): M11 casts each a
  voice and has their photograph and 3D head. One per viva.
- **The room** shows the examiner large beside the conversation — the head's
  mouth moves with the voice, it looks at the student while they speak — and
  speaks every examiner line (`useInterviewerVoice`; the browser's voice when
  M11 is down). The student answers aloud: the mic opens once the examiner
  has finished (not before — the voice takes seconds to make, and the room had
  said "your turn" in that gap), `useTurnTaking` decides when the answer is
  over, M11's recogniser writes it down whole, and the answer goes with how
  long they waited (from the end of the question) and how long they spoke.
  "Repeat the question", "Give me a hint", "I don't know", and "Type instead"
  are always there; with M11's recogniser down the room says so and takes
  typing.
- **Short and long questions:** the bank asks for both — a one-line fact,
  or an explanation in a few sentences — and code decides which by the answer's
  points (one point = short). Crisp: a question over 28 words, or two joined
  by "and how/why/what…", is dropped. The viva alternates, opening short; the
  room says "a line will do" or "explain it in a few sentences".
- **Found live and fixed:** a lab banked under an older prompt kept serving
  its old questions (a banked page counted as done whatever it was banked
  under); the examiner's 3D head never loaded in M20's dev server (Vite did
  not pre-bundle the renderer, whose jszip import then failed, silently) —
  `optimizeDeps.include` in `vite.config.ts`; the wait before an answer was
  counted from the line appearing, not from the examiner finishing; a long
  greeting outlasted the "voice never started" timer. Verified in headless
  Edge with a recorded answer as the microphone: spoken, heard, transcribed
  word for word, timed (3.3 s wait, 6.5 s answer).

**The viva, as built (2026-10-28):**

- **Question bank (`bank.py`):** a page is banked the first time a viva needs
  it, for everyone after (`BankPage`) — with its whole part of ten pages, in
  one model call (Groq gpt-oss-120b, generation tier) that drafts up to 4
  questions a page, each with the words of the page it is drawn from, answer points with a follow-up that does not give
  them away, a hint and a difficulty. Code then drops any question whose quote
  is not on the page (AC-20.2), any answer point the page does not make (an
  acronym's expansion must be on the page whole), a third question on one
  sentence, and any hint or question that points at the page ("look at the
  Result line") — the student cannot see it during the viva. No model: questions
  by rule from definitions and a lab manual's Aim / Principle / Result.
- **The viva (`viva.py`):** greeting and an unmarked warm-up ("what is the aim
  of Lab 6?") while the first pages bank in the background; then questions in
  scope order, a different family each time, harder as it goes, not one this
  student was asked before if another will do. Correct → next. Partial → one
  follow-up for a missing point. Wrong or blank → a hint. Still not right →
  taught, with the page to reread. Three examiners; their words are written by
  rule, so a viva's only model call is marking.
- **Marking (`marking.py`):** the model says which points the answer reached,
  with the student's own words as evidence (found in the answer by code); a
  wrong answer needs the wrong words quoted. Code decides: correct / partial /
  missed (nothing reached, nothing wrong said) / incorrect (a contradiction) /
  blank. An attempt then "I don't know" keeps the attempt.
- **Report:** knew · read again (by page, with the quotes) · how you answered
  (fillers per 100 words — M06's count —, wait before answering, long waits,
  unfinished answers, words per answer; pace on spoken answers only) · the
  trend over the last five vivas once there are three · question by question.
- **Measured live (Groq, one key):** a page banks in ~2 s, an answer is marked
  in ~1 s; with the student's pauses the background bank stays ahead, so an
  answer comes back in ~1 s. Found live and fixed, each with a test: answers
  took 38–74 s and the background bank failed "database is locked" (a request
  held SQLite's write lock across the model call); "LRU stands for Least
  Recently Used" asked of a page that never says so; hints pointing at the
  page; "Now, Why…"; "missed" called "incorrect"; an attempt then "I don't
  know" read as blank; the report claiming the model was down when it was not.
- **Tests:** 111 backend (31 → 111), lint clean; frontend typecheck and build
  clean; the room driven in headless Edge (Enter sends, the wait is measured,
  hint works, no console errors).

- **Catalogue:** 20 programmes, 46 campus × branch offerings, 18 curricula
  read, 2,001 courses (948 in semesters, 1,053 electives). The data comes from
  amrita.edu (the curriculum page, each programme's page, each curriculum
  PDF) via `jobs.sync_catalogue`, and is stored in `packages/catalogue/amrita.json`.
  Branches per campus: Amritapuri 10, Coimbatore 16, Bengaluru 8, Chennai 7,
  Amaravati 5.
- **Folder tree:** `jobs.folders scaffold <dir>` (or *Download the empty
  folder tree* on the import page) writes Amrita University / Campus / Branch /
  Semester_1…8 + Electives / `CODE - Title`: 5 campuses, 46 branches, 5,526
  course folders. A copy is at `projects/Course_Viva_Material/`.
- **Import:** pick the folder in the browser. A dry run sends only file paths
  (empty bodies), so a large folder is planned in a second. The import then
  uploads only the placed files, in batches of 25 files or 40 MB, with
  progress. Re-running it adds nothing new (AC-20.5).
- **Hold for material shared without a stated permission (EC-20.8):** it is
  `held`, seen by its uploader and the placement cell until a curator approves.
  Curator uploads and folder imports need no hold.
- **Tests:** 24 backend tests (pytest), lint clean, typecheck and build clean.
  Every screen was crawled headless as a student and as the placement cell at
  1440 px: no errors, no overflow.

**Parse quality, measured, not assumed** (latest curriculum per programme):

| | Result |
|---|---|
| Curricula read | 18 of 19 in scope. AID (ME) 2024 failed: its PDF has no table the reader recognises |
| Semesters found | 129 of 152 (85%). Missing: AEE 5, 6, 8 · AID (AA&RS) 4, 7, 8 · AID (QT) 4, 7, 8 · AID (CPS&S) 1 · ARE 4–8 · CHE 1, 2, 3, 5 · CIE 5 · EEE 1 |
| Syllabus matched | 800 of 948 semester courses (84%), 709 of 1,053 electives (67%). AID (CPS&S): 2 of 57 |
| Unplaced rows | 114 table rows read without a code (e.g. AEE semester 5, CHE). Kept as warnings in each curriculum, not guessed |

A semester the reader missed shows as an empty tab with *"the PDF has no
course table the library could read"* and a link to the PDF. It is never
silently dropped.

## Next (in order)

1. **Parser, round 2.** The missing semesters and AID (ME): these PDFs lay
   out tables with rows that carry no code (title + L-T-P only). Match those
   rows to syllabus pages by title, and read AID (ME)'s layout. Target: AC-20.4
   at ≥ 90% of semesters.
2. **Older regulation years.** A 4th-year student today is on 2022 or an
   earlier curriculum: parse the previous year too (34 curricula are listed
   but unread). Each is one more PDF through the same reader.
3. **Fill the library.** The placement cell fills `Course_Viva_Material` and
   imports it, then times one semester's folder (AC-20.7). The viva needs
   material with text: today a test lab (23CSE214, Lab 6) and the user's
   59-page RL deck (25AID301, private to the dev student) are what there is.
4. **Pictures with no text.** 13 of that deck's 59 slides are images —
   diagrams, the TD update drawn as a figure, the numerical example — and the
   viva can only name them. OCR, or a vision model reading the slide, is the
   open decision 3 below.
5. **From the product research (2026-10-28):** after a right short answer,
   the "why" question on the same passage (Sherpa probes a strong answer
   deeper); "practise what you missed" — a viva on the questions got wrong
   (NotebookLM reruns missed cards); a near-duplicate check in the bank (the
   L2Q paper); the page before a part as context (overlapping windows, the
   slide-deck question paper); the topics of each part on the start panel;
   hedges ("I think", "maybe") among the speaking measures; the examiner
   cutting in when a one-line question gets a long ramble.
6. **Results to M04 behind consent (FR-20.20).**

## 1. The plan (project manager's view)

| Phase | Goal | Work | Done when | Owner (suggested) |
|---|---|---|---|---|
| **0** | The module exists | Spec, this TODO, repo `Course_Viva` with `main` + `todo`, skeleton on 8120/5220, PORTS.txt row | `/health` answers; the plan is on `todo` | Ansh |
| **1** | **The library, loaded** | Data model; catalogue sync from amrita.edu (programmes, regulation years, curriculum PDFs, the campus matrix); course syllabi from the PDFs; folder scaffold + import; upload; text extraction; search; browse UI | Five campuses → their real branches → semesters → courses browse; a folder of notes imports in one command | Ansh / E3 |
| **2** | **A viva on your material** | Page-chunked question bank with cited spans; viva room (typed first, then voice via M11); marking against the span; hint → teach; report | A student is vivaed on a lab manual and gets a page-cited report | E2 |
| **3** | **Speaking skills** | Pace, fillers, silences, unfinished answers; trends over vivas; lab-viva mode | A student's measures are shown and trend | E1 |
| **4** | **Part of the platform** | Platform sign-in; "Library" and "Viva" in the shell; M04 evidence behind consent; curator review queue; coverage view | A student signed in on :5173 opens their course and vivas | Ansh |

**Risks, and what we do about them**

| Risk | Mitigation |
|---|---|
| The university changes its pages or PDF layout | Every row keeps its source URL and date; a parse failure leaves a curriculum `listed`, never half-filled; re-sync is one command |
| Copyright on uploaded material | Visibility + permission + takedown from day one (FR-20.11); nothing public on the internet |
| Model allowance (200K tokens/day/model) | Questions generated once per page-chunk and cached; a viva spends calls only on follow-ups and marking |
| Scanned PDFs (no OCR) | Stored and shown, `no_text`; OCR is an open decision |
| Two curriculum parsers drifting (M04's and ours) | Phase 4: move the reader into Platform_Core so both use one |

## 2. Functional requirements

| FR | | Priority |
|---|---|---|
| FR-20.1 | ✅ Hierarchy institution → campus → offered programme → curriculum → semester → course → material | P0 |
| FR-20.2 | ✅ Catalogue synced from the university's pages and PDFs, with provenance; idempotent | P0 |
| FR-20.3 | 🟡 A campus shows only its programmes; a programme its semesters and courses per regulation year — *the latest year is read; older years are listed with their PDFs, not read (Next 2)* | P0 |
| FR-20.4 | ✅ Course syllabus text from the curriculum PDF, as the course's first material | P0 |
| FR-20.5 | ✅ Upload material (PDF/DOCX/PPTX/images/links) with kind and unit/lab | P0 |
| FR-20.6 | ✅ Bulk import from a folder tree mirroring the hierarchy, dry-run first, idempotent by hash | P0 |
| FR-20.7 | ✅ Scaffold the empty folder tree for every campus/branch/semester/course | P0 |
| FR-20.8 | ✅ Text extraction per page; `no_text` for scans | P0 |
| FR-20.9 | 🟡 Full-text search with campus/branch/semester/course filters — *FTS5 over pages and courses, code/title matches ranked above syllabus mentions; the API filters by branch and semester, the UI has no filters yet* | P1 |
| FR-20.10 | ✅ Material shared across campuses by default; campus tag when local | P0 |
| FR-20.11 | 🟡 Visibility, provenance and takedown — *private / held / platform, who / when / permission, takedown everywhere; the spec's "my campus" visibility is not built* | P0 |
| FR-20.12 | ✅ Coverage view: what is still empty | P1 |
| FR-20.13 | ✅ Viva scope: course, units, labs, documents/pages — *`GET /v1/vivas/scope/{course}`; a scan or a link is left out and named; the UI offers course / unit / document, and a long document ten pages at a time* | P0 |
| FR-20.14 | ✅ Question bank per page-chunk, each question citing its span — *banked once per ten-page part, cited, checked; the placement cell reviews it at `/library/questions/:material`* | P0 |
| FR-20.15 | ✅ Viva session: examiner persona, spoken or typed, follow-ups, hint then teach — *seen (3D head or photo) and heard through M11; answered aloud or typed* | P0 |
| FR-20.16 | ✅ Marking against the cited span — *correct / partial / missed / incorrect / blank, with what was reached and what was missing* | P0 |
| FR-20.17 | ✅ Speaking measures: pace, fillers, silences, answer length, unfinished answers — *pace and silences from spoken answers' timings (the wait counted from the end of the question); typed answers say pace is not measured* | P0 |
| FR-20.18 | ✅ Report: knew / reread (page-cited) / how you sounded, with trend | P0 |
| FR-20.19 | ✅ Lab viva mode — *principle → procedure → observations → result → precautions → sources of error, the aim as the warm-up* | P1 |
| FR-20.20 | ⬜ Results to M04 behind consent | P1 |
| FR-20.21 | ✅ Platform sign-in and shell entries — *"Viva practice" and "Course library" in Platform_Shell, on the platform's session* | P0 |

## 3. Acceptance gates

| AC | | Target |
|---|---|---|
| AC-20.1 **[GATE]** | ✅ Every campus shows exactly the programmes its programme pages list | 100% on sync |
| AC-20.2 **[GATE]** | ✅ Every viva question cites a span that is in its page — *enforced in `bank.check`; two gate tests, one over a whole viva* | 100% |
| AC-20.3 **[GATE]** | ✅ Nothing uploaded is visible beyond its visibility setting | 100% |
| AC-20.4 | 🟡 Courses parsed for the latest curriculum of every in-scope programme — *85% of semesters (129 / 152)* | ≥ 90% |
| AC-20.5 | ✅ Folder import re-run creates nothing new | 0 duplicates |
| AC-20.6 | 🟡 Speaking measures improve over five vivas — *the trend is computed and shown once there are three vivas; nobody has sat five yet* | reported |
| AC-20.7 | ⬜ A semester's folder loads in under five minutes | measured |

## 4. Edge cases

Spec §9.

- ✅ EC-20.1 a branch at one campus only · EC-20.2 an unreadable PDF stays unread with its PDFs
  linked (AID (ME)) · EC-20.3 combined "&" links dropped · EC-20.7 elective baskets listed by
  slot · EC-20.8 no permission → held · EC-20.9 takedown everywhere — search, views and now the
  question bank —, and the file cannot quietly return · EC-20.10 the same file twice is one
  material · EC-20.5 a scan is stored as `no_text`, and a viva leaves it out and says why
- 🟡 EC-20.4 one material, but tagged with the first campus only · EC-20.6 the year can be
  switched; older years are not read yet

## 5. Open decisions (for the user)

1. Scope beyond B.Tech + AI (M.Tech, B.Sc., …)?
2. Campuses beyond the five (Nagercoil, Haridwar, Faridabad also run B.Tech)?
3. OCR for scanned lab manuals — and for slides that are only a picture (13 of 59 in the RL deck)? A vision model on Groq could read a slide's image; it is a model call per picture.
4. Who may upload — students, or faculty and class representatives only?
5. Pre-2019 curricula (two-PDF layout): parse, or link only?
