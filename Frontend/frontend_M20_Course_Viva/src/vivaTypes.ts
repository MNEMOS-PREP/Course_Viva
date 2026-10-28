/**
 * M20 — Course Viva · the viva's shapes, copied field for field from
 * backend_M20_Course_Viva/viva.py (`state`, `report`, `history`) and
 * viva_router.py (`scope`). A field the backend does not send is not here.
 */

import type { MaterialKind } from "./types";

/** How an answer was marked (marking.py). `missed`: nothing reached, nothing
 *  wrong said. `incorrect`: a contradiction, in the student's own words. */
export type AnswerStatus = "correct" | "partial" | "missed" | "incorrect" | "blank";
export type ItemStatus = AnswerStatus | "not_answered";
/** short: one fact in a line · long: explained in a few sentences. */
export type AnswerLength = "short" | "long";
/** course: the material, page by page · lab: an experiment's steps, in a lab
 *  examiner's order (FR-20.19). */
export type VivaStyle = "course" | "lab";
/** A lab viva's steps, in the order they are asked (bank.LAB_STAGES). */
export type LabStage =
  | "principle"
  | "procedure"
  | "observations"
  | "result"
  | "precautions"
  | "sources of error"
  | "aim";

/** Ten pages of a long document (bank.PART_PAGES): what a viva takes at a time. */
export interface VivaPart {
  part: number;
  first: number;
  last: number;
  pages_with_text: number;
  /** Pages with no text at all: a diagram, or an equation drawn as a picture. */
  picture_pages: number[];
  /** Pages with only a few words: a title slide. */
  title_pages: number[];
  questions: number;
  /** Its questions are banked: the viva starts without waiting. */
  ready: boolean;
  /** This student finished a viva on it. */
  done: boolean;
}

/** The pages of one document a viva is on (viva.span_of). */
export interface VivaSpan {
  material_id: string;
  first: number;
  last: number;
}

/** The next part with something to ask, after the one a viva was on
 *  (viva.next_part): a part of only pictures is passed over. */
export interface NextPart {
  material_id: string;
  title: string;
  first: number;
  last: number;
  pages_with_text: number;
  ready: boolean;
}

/** One of the platform's academic interviewers: M11 casts the voice
 *  (`voice_id`) and has the photograph and, mostly, a 3D head (`id`). */
export interface Examiner {
  id: string;
  name: string;
  title: string;
  voice_id: string;
}

export interface VivaScope {
  /** Who examines this student's next viva (the four take turns). */
  examiner: Examiner;
  /** The opening lines said whatever is chosen: made ahead by M11. */
  say_first: string[];
  course: { id: string; code: string; title: string };
  materials: {
    id: string;
    title: string;
    kind: MaterialKind;
    unit: string | null;
    pages: number;
    /** Pages with enough text to be examined on. */
    usable_pages: number;
    /** Questions already banked from it. */
    questions: number;
    /** Ten pages at a time, for a document longer than ten; else empty. */
    parts: VivaPart[];
    /** Its picture pages are being read now, a few a minute (reading.py). */
    reading: boolean;
  }[];
  units: string[];
  excluded: { material_id: string; title: string; why: string }[];
  ready: boolean;
}

export interface Cite {
  material_id: string;
  title: string;
  kind: string;
  page: number;
  quote: string;
  span_start: number;
  span_end: number;
  /** The page was a picture, read by a model: the quote is what it read. */
  read_from_picture: boolean;
}

export type TurnKind =
  | "greeting"
  | "warmup"
  | "question"
  | "follow_up"
  | "hint"
  | "teach"
  | "ack"
  | "close"
  | "answer";

export interface VivaTurn {
  seq: number;
  role: "examiner" | "student";
  kind: TurnKind;
  text: string;
  item: number;
  /** Only once the question it belongs to is closed (spec §2.3). */
  cite?: Cite;
  verdict?: AnswerStatus;
}

export interface VivaState {
  id: string;
  status: "live" | "ended";
  end_reason: "complete" | "ended_by_student" | "replaced" | null;
  mode: "typed" | "spoken";
  style: VivaStyle;
  course: { id: string; code: string; title: string } | null;
  scope: { label: string; excluded: { material_id: string; title: string; why: string }[] };
  /** A viva on ten pages of a longer document: which ten. */
  part: VivaSpan | null;
  examiner: Examiner;
  target: number;
  asked: number;
  turns: VivaTurn[];
  open: {
    item: number;
    kind: "warmup" | "question";
    stage: "asked" | "follow_up" | "hint";
    hint_available: boolean;
    /** A line, or a few sentences; null for the warm-up. */
    answer_length: AnswerLength | null;
  } | null;
  started_at: string;
  ended_at: string | null;
  /** Once ended, for a viva on part of a document: the part after it. */
  next_part: NextPart | null;
}

export interface Measures {
  words: number;
  fillers: Record<string, number>;
  filler_count: number;
  silence_ms: number | null;
  wpm: number | null;
  spoken: boolean;
  unfinished: boolean;
}

export interface Sounded {
  answers: number;
  words: number;
  words_per_answer: number | null;
  fillers: number;
  fillers_per_100: number | null;
  top_filler: string | null;
  silence_ms_median: number | null;
  long_silences: number;
  wpm: number | null;
  spoken_answers: number;
  unfinished: number;
}

export interface ReportItem {
  item: number;
  question: string;
  family: string | null;
  /** A lab viva's step; null on a course viva. */
  stage: LabStage | null;
  difficulty: number | null;
  answer_length: AnswerLength | null;
  status: ItemStatus;
  help: ("follow_up" | "hint" | "taught")[];
  answers: { text: string; status: AnswerStatus | null; measures: Measures }[];
  covered: string[];
  missing: string[];
  wrong: { said: string; why: string } | null;
  marked_by: string | null;
  cite: Cite | null;
  /** The model's id, or "rules" for a question written by rule. */
  written_by: string | null;
  reviewed: boolean;
  exchange: { role: "examiner" | "student"; kind: TurnKind; text: string }[];
}

export interface VivaReport {
  viva: {
    id: string;
    course: { id: string; code: string; title: string } | null;
    scope: string;
    part: VivaSpan | null;
    examiner: string;
    mode: "typed" | "spoken";
    style: VivaStyle;
    status: "live" | "ended";
    end_reason: string | null;
    target: number;
    started_at: string;
    ended_at: string | null;
  };
  /** For a viva on part of one document: the pages asked from, and those
   *  with nothing to ask (pictures). */
  coverage: {
    material_id: string;
    title: string;
    first: number;
    last: number;
    asked_from: number[];
    picture_pages: number[];
    title_pages: number[];
  } | null;
  next_part: NextPart | null;
  counts: Record<ItemStatus, number>;
  items: ReportItem[];
  knew: number[];
  reread: { material_id: string; title: string; page: number; quotes: string[]; items: number[] }[];
  sounded: Sounded;
  trend: {
    vivas: number;
    fillers_per_100: (number | null)[];
    silence_ms_median: (number | null)[];
    fillers: "better" | "worse" | "steady" | null;
    silences: "better" | "worse" | "steady" | null;
  } | null;
  marked_by_rules: boolean;
}

export interface VivaSummary {
  id: string;
  course: { id: string; code: string; title: string } | null;
  scope: string;
  part: VivaSpan | null;
  status: "live" | "ended";
  mode: "typed" | "spoken";
  style: VivaStyle;
  started_at: string;
  target: number;
  correct: number;
  answered: number;
}

export interface StartVivaInput {
  course_id: string;
  material_ids?: string[];
  unit?: string;
  /** {material_id: [first page, last page]} */
  pages?: Record<string, [number, number]>;
  mode?: "typed" | "spoken";
  style?: VivaStyle;
  questions?: number;
}

export interface AnswerTiming {
  silence_ms?: number;
  duration_ms?: number;
  spoken?: boolean;
}

/** A question in the bank, as the placement cell reviews it
 *  (viva_router._question_out). */
export interface BankQuestion {
  id: string;
  material_id: string;
  page: number;
  family: string;
  answer_length: AnswerLength;
  text: string;
  quote: string;
  answer_points: { point: string; probe: string }[];
  hint: string;
  difficulty: number;
  status: "draft" | "reviewed" | "retired";
  /** The model's id, or "rules". */
  written_by: string;
  /** Its page was a picture, read by a model: worth checking against the slide. */
  read_from_picture: boolean;
  /** Written under the bank's current prompt; an older one is rewritten when
   *  a viva next reaches its page. */
  current: boolean;
}

/** A material's bank (GET /v1/vivas/bank/{material_id}). */
export interface MaterialBank {
  material: { id: string; course_id: string; title: string; pages: number };
  pages_banked: number;
  /** Banked pages that gave no question, and why. */
  skipped: { page: number; why: string }[];
  questions: BankQuestion[];
}
