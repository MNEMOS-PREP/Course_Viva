/**
 * Small pieces every library screen uses: the trail back up the tree, the
 * words for a material's kind, and a pill.
 */

import { Fragment } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { MaterialKind } from "../types";

export const ROOT = "/library";

/** The library's tree is the folder tree: campus › branch › semester › course. */
export const paths = {
  campus: (campus: string) => `${ROOT}/${campus}`,
  programme: (campus: string, programme: string, opts: { year?: number; sem?: string } = {}) => {
    const query = new URLSearchParams();
    if (opts.year) query.set("year", String(opts.year));
    if (opts.sem) query.set("sem", opts.sem);
    const tail = query.toString();
    return `${ROOT}/${campus}/${programme}${tail ? `?${tail}` : ""}`;
  },
  course: (campus: string, programme: string, year: number, code: string) =>
    `${ROOT}/${campus}/${programme}/${year}/${encodeURIComponent(code)}`,
};

/** "btech-cse-2023:23CSE201" → its programme, year and code. */
export function splitCourseId(id: string): { programme: string; year: number; code: string } {
  const [curriculum, code] = id.split(":");
  const at = curriculum.lastIndexOf("-");
  return { programme: curriculum.slice(0, at), year: Number(curriculum.slice(at + 1)), code };
}

const CAMPUS_KEY = "m20.campus";

/** The campus a student last browsed: where a search hit should take them. */
export function rememberCampus(campus: string): void {
  try {
    localStorage.setItem(CAMPUS_KEY, campus);
  } catch {
    /* private mode: search links fall back to the first campus */
  }
}

export function campusFor(campuses: string[]): string | undefined {
  let held: string | null = null;
  try {
    held = localStorage.getItem(CAMPUS_KEY);
  } catch {
    /* private mode */
  }
  return held && campuses.includes(held) ? held : campuses[0];
}

export function Trail({ items }: { items: { label: ReactNode; to?: string }[] }) {
  return (
    <nav aria-label="Where you are" className="mb-4 flex flex-wrap items-center gap-1.5 text-sm">
      {items.map((item, i) => (
        <Fragment key={i}>
          {i > 0 && (
            <span aria-hidden className="text-ink-faint">
              ›
            </span>
          )}
          {item.to ? (
            <Link to={item.to} className="text-ink-soft hover:text-brand">
              {item.label}
            </Link>
          ) : (
            <span aria-current="page" className="font-medium text-ink">
              {item.label}
            </span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}

export const KIND_LABEL: Record<MaterialKind, string> = {
  syllabus: "Syllabus",
  notes: "Notes",
  slides: "Slides",
  lab_manual: "Lab manuals",
  question_paper: "Question papers",
  reference: "References",
  video: "Videos",
  other: "Other",
};

/** The order a student preparing a viva reaches for them. */
export const KIND_ORDER: MaterialKind[] = [
  "notes",
  "slides",
  "lab_manual",
  "question_paper",
  "syllabus",
  "reference",
  "video",
  "other",
];

type Tone = "neutral" | "brand" | "confirmed" | "reported" | "contested";

const TONES: Record<Tone, string> = {
  neutral: "border-line bg-surface-sunken text-ink-soft",
  brand: "border-brand-line bg-brand-soft text-brand",
  confirmed: "border-confirmed-line bg-confirmed-soft text-confirmed",
  reported: "border-reported-line bg-reported-soft text-reported",
  contested: "border-contested-line bg-contested-soft text-contested",
};

export function Pill({
  tone = "neutral",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

export function sizeOf(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
