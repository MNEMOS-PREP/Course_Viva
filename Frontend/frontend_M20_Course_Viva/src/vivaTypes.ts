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

export interface VivaScope {
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
  course: { id: string; code: string; title: string } | null;
  scope: { label: string; excluded: { material_id: string; title: string; why: string }[] };
  /** One of the platform's academic interviewers: M11 casts the voice
   *  (`voice_id`) and has the photograph and, mostly, a 3D head (`id`). */
  examiner: { id: string; name: string; title: string; voice_id: string };
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
    examiner: string;
    mode: "typed" | "spoken";
    status: "live" | "ended";
    end_reason: string | null;
    target: number;
    started_at: string;
    ended_at: string | null;
  };
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
  status: "live" | "ended";
  mode: "typed" | "spoken";
  started_at: string;
  target: number;
  correct: number;
  answered: number;
}

export interface StartVivaInput {
  course_id: string;
  material_ids?: string[];
  unit?: string;
  mode?: "typed" | "spoken";
  questions?: number;
}

export interface AnswerTiming {
  silence_ms?: number;
  duration_ms?: number;
  spoken?: boolean;
}
