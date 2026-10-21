/**
 * M20 — Course Viva · the shapes the backend sends.
 *
 * Copied from backend_M20_Course_Viva/library.py and router.py, field for field.
 * A field the backend does not send is not declared here (stubs must copy the
 * producer).
 */

export interface Institution {
  id: string;
  name: string;
  display: string;
}

export interface Campus {
  id: string;
  institution_id: string;
  name: string;
  position: number;
}

export interface Programme {
  id: string;
  institution_id: string;
  degree: string;
  name: string;
  short: string;
  school: string;
  source_url: string | null;
  /** Campuses the programme page names outside the five this library covers. */
  also_at: string[];
}

export interface CurriculumDocument {
  label: string;
  url: string;
}

export interface Tree {
  institution: Institution | null;
  campuses: (Campus & { programmes: number })[];
}

export interface CampusProgramme extends Programme {
  curriculum_year: number | null;
  curriculum_status: string | null;
  courses: number;
  materials: number;
}

export interface CampusView {
  campus: Campus;
  programmes: CampusProgramme[];
}

export interface CourseRow {
  id: string;
  code: string;
  title: string;
  /** A string: "3", "P/F", "[3]" — the curriculum's own words. */
  credits: string | null;
  ltp: string | null;
  category: string | null;
  has_syllabus: boolean;
  materials: number;
}

export interface ProgrammeView {
  programme: Programme;
  campuses: Campus[];
  curricula: { id: string; year: number; status: string; documents: CurriculumDocument[] }[];
  curriculum: {
    id: string;
    year: number;
    status: string;
    documents: CurriculumDocument[];
    parsed_from: string | null;
    slots: Record<string, unknown[]>;
  } | null;
  semesters: { number: number; courses: CourseRow[] }[];
  electives: { name: string; courses: CourseRow[] }[];
}

export type MaterialKind =
  | "syllabus"
  | "notes"
  | "slides"
  | "lab_manual"
  | "question_paper"
  | "reference"
  | "video"
  | "other";

export interface Material {
  id: string;
  course_id: string;
  campus_id: string | null;
  title: string;
  kind: MaterialKind;
  unit: string | null;
  filename: string | null;
  url: string | null;
  mime: string | null;
  bytes: number;
  pages: number;
  text_status: "pending" | "ok" | "no_text" | "failed" | "link";
  /** `held`: asked for everyone, no permission stated — waits for a curator. */
  visibility: "private" | "held" | "platform";
  permission: string | null;
  added_by: string;
  status: "published" | "removed";
  created_at: string;
}

export interface Course {
  id: string;
  curriculum_id: string;
  code: string;
  title: string;
  semester: number | null;
  basket: string | null;
  category: string | null;
  ltp: string | null;
  credits: string | null;
  syllabus: string | null;
  syllabus_page: number | null;
}

export interface CourseView {
  course: Course;
  curriculum: {
    id: string;
    year: number;
    documents: CurriculumDocument[];
    /** The PDF the syllabus and its page number were read from. */
    parsed_from: string | null;
  } | null;
  programme: Programme | null;
  materials: Material[];
}

export interface MaterialPages {
  material: Material;
  pages: { page: number; text: string }[];
}

export interface SearchResult {
  courses: {
    id: string;
    code: string;
    title: string;
    semester: number | null;
    programme_id: string;
    programme: string;
    short: string;
    year: number;
    /** Campuses that run its programme, in campus order. */
    campuses: string[];
    /** A syllabus match only mentions the words; code and title are the course. */
    match: "code" | "title" | "syllabus";
  }[];
  pages: {
    material_id: string;
    title: string;
    kind: MaterialKind;
    page: number;
    /** FTS5's snippet: the matched words are wrapped in [ and ]. */
    snippet: string;
    course_id: string;
    course: string;
    campuses: string[];
  }[];
}

export interface CoverageRow {
  campus: string;
  campus_id: string;
  programme_id: string;
  programme: string;
  short: string;
  year: number | null;
  courses: number;
  with_material: number;
}

export interface Placement {
  path: string;
  course_id: string;
  campus_id: string;
  kind: MaterialKind;
  unit: string | null;
}

export interface ImportDryRun {
  dry_run: true;
  would_add: Placement[];
  problems: { path: string; reason: string }[];
}

export interface ImportDone {
  dry_run: false;
  added: number;
  already_there: number;
  problems: { path: string; reason: string }[];
}

export interface Health {
  status: string;
  module: string;
  catalogue_fetched_at: string | null;
  programmes: number;
  courses: number;
  materials: number;
}
