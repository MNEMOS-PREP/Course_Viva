/**
 * "Go on to pages 11–20". A long document is taken ten pages at a time, and
 * the next ten are banked while the student answers these, so the next
 * sitting starts without a wait.
 */

import { useNavigate } from "react-router-dom";

import { Icon } from "@ai/core";

import { useStartViva } from "../vivaApi";
import type { NextPart as Next, VivaSpan, VivaStyle } from "../vivaTypes";

export function pagesLabel(first: number, last: number): string {
  return first === last ? `page ${first}` : `pages ${first}–${last}`;
}

/** "TD learning · pages 11–20" for a viva on a part, else the scope as it is. */
export function scopeLabel(scope: string, part: VivaSpan | null): string {
  return part ? `${scope} · ${pagesLabel(part.first, part.last)}` : scope;
}

export function NextPart({
  next,
  courseId,
  mode,
  style,
  questions,
  className = "",
}: {
  next: Next;
  courseId: string;
  mode: "typed" | "spoken";
  style: VivaStyle;
  questions: number;
  className?: string;
}) {
  const start = useStartViva();
  const navigate = useNavigate();
  const go = () =>
    start.mutate(
      {
        course_id: courseId,
        material_ids: [next.material_id],
        pages: { [next.material_id]: [next.first, next.last] },
        mode,
        style,
        questions,
      },
      { onSuccess: (state) => navigate(`/viva/${state.id}`) },
    );
  return (
    <div className={className}>
      <button
        type="button"
        onClick={go}
        disabled={start.isPending}
        className="inline-flex h-9 items-center gap-2 rounded-lg border border-brand-line bg-brand-soft px-4 text-sm font-semibold text-brand hover:border-brand disabled:opacity-60"
      >
        {start.isPending ? "Getting the examiner ready…" : `Go on to ${pagesLabel(next.first, next.last)}`}
        <Icon name="arrowRight" size={14} />
      </button>
      <p className="mt-1.5 text-xs text-ink-faint" data-numeric>
        {next.ready
          ? "Its questions are ready — they were prepared while you answered these."
          : "Its questions are still being prepared; the warm-up gives them time."}
      </p>
      {start.error && <p className="mt-1 text-xs text-contested">{start.error.message}</p>}
    </div>
  );
}
