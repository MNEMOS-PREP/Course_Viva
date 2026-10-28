/**
 * How an answer went, drawn the same way everywhere: a colour, a shape and a
 * word, so colour is never the only signal (WCAG 1.4.1) — the platform's
 * interview notes draw theirs the same way.
 */

import type { ReactNode } from "react";

import type { ItemStatus } from "../vivaTypes";

interface Meta {
  label: string;
  badge: string;
  accent: string;
  shape: ReactNode;
}

const SHAPE = {
  check: <path d="M3.5 8.5l3 3 6-6.5" />,
  half: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor" />
    </>
  ),
  wave: <path d="M2 9c1.5-2.5 3-2.5 4 0s2.5 2.5 4 0 2.5-2.5 4 0" />,
  cross: <path d="M4.5 4.5l7 7m0-7l-7 7" />,
  circle: <circle cx="8" cy="8" r="5.5" />,
  dash: <path d="M4.5 8h7" />,
};

export const VERDICT: Record<ItemStatus, Meta> = {
  correct: {
    label: "Correct",
    badge: "border-confirmed-line bg-confirmed-soft text-confirmed",
    accent: "border-l-confirmed",
    shape: SHAPE.check,
  },
  partial: {
    label: "Partly there",
    badge: "border-reported-line bg-reported-soft text-reported",
    accent: "border-l-reported",
    shape: SHAPE.half,
  },
  missed: {
    label: "Missed the point",
    badge: "border-agreement-line bg-agreement-soft text-agreement",
    accent: "border-l-agreement",
    shape: SHAPE.wave,
  },
  incorrect: {
    label: "Incorrect",
    badge: "border-contested-line bg-contested-soft text-contested",
    accent: "border-l-contested",
    shape: SHAPE.cross,
  },
  blank: {
    label: "Didn't know",
    badge: "border-line-strong bg-surface-sunken text-ink-soft",
    accent: "border-l-line-strong",
    shape: SHAPE.circle,
  },
  not_answered: {
    label: "Not answered",
    badge: "border-line bg-surface-sunken text-ink-faint",
    accent: "border-l-line",
    shape: SHAPE.dash,
  },
};

export const VERDICT_ORDER: ItemStatus[] = [
  "correct",
  "partial",
  "missed",
  "incorrect",
  "blank",
  "not_answered",
];

export function VerdictBadge({ status, size = "md" }: { status: ItemStatus; size?: "sm" | "md" }) {
  const meta = VERDICT[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${meta.badge} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs"
      }`}
    >
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        width={size === "sm" ? 11 : 13}
        height={size === "sm" ? 11 : 13}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {meta.shape}
      </svg>
      {meta.label}
    </span>
  );
}

/** What help a question took, in words. */
export const HELP_LABEL: Record<"follow_up" | "hint" | "taught", string> = {
  follow_up: "after a follow-up",
  hint: "after a hint",
  taught: "explained to you",
};
