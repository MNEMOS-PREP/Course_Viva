/**
 * The placement cell reviews a material's viva questions (FR-20.14).
 *
 * Every question was checked by code before it was kept — its quote is on its
 * page (AC-20.2), its answer points are the page's own words — so what a
 * person adds is judgement: is this what an examiner would ask, and is the
 * answer the page gives the right one? A reviewed question says so in the
 * student's report; a retired one is never asked again, and can be restored.
 */

import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { EmptyState, ErrorNote, PageHeader, SkeletonRows, isStaff, useSession } from "@ai/core";

import { Pill, ROOT, plural } from "../ui/bits";
import { useBank, useReviewQuestion } from "../vivaApi";
import type { BankQuestion } from "../vivaTypes";

type Show = "to_review" | "reviewed" | "all";

const SHOWN: Record<Show, (q: BankQuestion) => boolean> = {
  to_review: (q) => q.status === "draft",
  reviewed: (q) => q.status === "reviewed",
  all: () => true,
};

const SHOW_LABEL: Record<Show, string> = {
  to_review: "To review",
  reviewed: "Reviewed",
  all: "All, with retired",
};

const DIFFICULTY = ["", "recall", "understanding", "application"];

/** Pages with no question, grouped by why ("too short to examine …"). */
function skippedBy(skipped: { page: number; why: string }[]): [string, number[]][] {
  const by = new Map<string, number[]>();
  for (const s of skipped) {
    const why = s.why || "nothing on it could be asked about";
    by.set(why, [...(by.get(why) ?? []), s.page]);
  }
  return [...by.entries()];
}

export function QuestionReview() {
  const session = useSession();
  const { materialId = "" } = useParams();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [show, setShow] = useState<Show>("to_review");
  const bank = useBank(materialId, show === "all");
  const review = useReviewQuestion(materialId);

  if (!isStaff(session)) {
    return (
      <EmptyState title="Reviewing questions is the placement cell's" icon="shield">
        A student meets these questions in a viva, and sees each one's page afterwards.
      </EmptyState>
    );
  }
  if (bank.isPending) return <SkeletonRows label="Loading the questions" rows={5} />;
  if (bank.isError) {
    return <ErrorNote message="The questions did not load." detail={bank.error.message} onRetry={() => bank.refetch()} />;
  }

  const b = bank.data;
  const shown = b.questions.filter(SHOWN[show]);
  const pages = [...new Set(shown.map((q) => q.page))].sort((x, y) => x - y);
  const waiting = b.questions.filter((q) => q.status === "draft").length;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to={from ?? ROOT} className="text-sm text-brand hover:underline">
        ← Back to the course
      </Link>
      <PageHeader
        eyebrow="Viva questions"
        title={b.material.title}
        subtitle={`${plural(b.questions.filter((q) => q.status !== "retired").length, "question")} from ${b.pages_banked} of ${plural(b.material.pages, "page")} · ${waiting} to review`}
      />
      {b.pages_banked < b.material.pages && (
        <p className="text-sm text-ink-soft">
          Pages are given their questions when a viva first reaches them, ten at a time, so a page
          no viva has reached yet has none to review.
        </p>
      )}
      {skippedBy(b.skipped).map(([why, pages]) => (
        <p key={why} className="text-sm text-ink-soft" data-numeric>
          No questions on {pages.length === 1 ? "page" : "pages"} {pages.join(", ")}: {why}.
        </p>
      ))}

      <div role="group" aria-label="Show" className="inline-flex gap-1 rounded-lg border border-line p-0.5">
        {(Object.keys(SHOW_LABEL) as Show[]).map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={show === key}
            onClick={() => setShow(key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              show === key ? "bg-brand-soft text-brand" : "text-ink-soft hover:text-ink"
            }`}
          >
            {SHOW_LABEL[key]}
          </button>
        ))}
      </div>

      {review.error && <ErrorNote message="That did not go through." detail={review.error.message} />}

      {shown.length === 0 ? (
        <p className="text-sm text-ink-soft">
          {show === "to_review" ? "Nothing waits for review." : "No questions here."}
        </p>
      ) : (
        pages.map((page) => (
          <section key={page} aria-labelledby={`page-${page}`} className="space-y-3">
            <h2 id={`page-${page}`} className="eyebrow" data-numeric>
              Page {page}
            </h2>
            {shown
              .filter((q) => q.page === page)
              .map((q) => (
                <QuestionCard
                  key={q.id}
                  question={q}
                  busy={review.isPending}
                  onStatus={(status) => review.mutate({ id: q.id, status })}
                />
              ))}
          </section>
        ))
      )}
    </div>
  );
}

function QuestionCard({
  question: q,
  busy,
  onStatus,
}: {
  question: BankQuestion;
  busy: boolean;
  onStatus: (status: BankQuestion["status"]) => void;
}) {
  const button = (label: string, status: BankQuestion["status"], tone: string) => (
    <button
      type="button"
      disabled={busy}
      onClick={() => onStatus(status)}
      className={`rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-60 ${tone}`}
    >
      {label}
    </button>
  );
  return (
    <article className={`rounded-xl border bg-surface p-5 ${q.status === "retired" ? "border-line opacity-70" : "border-line"}`}>
      <header className="flex flex-wrap items-center gap-2 text-xs">
        {q.status === "reviewed" && <Pill tone="confirmed">reviewed</Pill>}
        {q.status === "retired" && <Pill tone="contested">retired</Pill>}
        {q.status === "draft" && <Pill tone="brand">to review</Pill>}
        <span className="text-ink-faint">
          {q.answer_length === "short" ? "Short answer" : "Long answer"} · {q.family}
          {DIFFICULTY[q.difficulty] ? ` · ${DIFFICULTY[q.difficulty]}` : ""} ·{" "}
          {q.written_by === "rules" ? "written by rule" : "written by a model"}
        </span>
        {q.read_from_picture && (
          <Pill
            tone="reported"
            title="This page is a picture: a model read its words, and the question and its quote come from what it read. Check them against the slide."
          >
            read from a picture
          </Pill>
        )}
        {!q.current && (
          <Pill title="Written under an older prompt: this page is given new questions when a viva next reaches it.">
            older version
          </Pill>
        )}
      </header>
      <h3 className="mt-2 font-semibold leading-snug text-ink">{q.text}</h3>
      <blockquote className="mt-2 border-l-2 border-brand-line pl-3 text-sm leading-relaxed text-ink-soft">
        {q.quote}
      </blockquote>
      <div className="mt-3">
        <p className="eyebrow mb-1">A good answer says</p>
        <ul className="space-y-1.5 text-sm text-ink">
          {q.answer_points.map((p) => (
            <li key={p.point}>
              {p.point}
              <span className="block text-xs text-ink-faint">If it is left out: “{p.probe}”</span>
            </li>
          ))}
        </ul>
      </div>
      {q.hint && (
        <p className="mt-3 text-sm text-ink-soft">
          <span className="font-medium text-ink">Hint: </span>
          {q.hint}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {q.status === "draft" && button("Mark reviewed", "reviewed", "border-confirmed-line text-confirmed hover:bg-confirmed-soft")}
        {q.status === "reviewed" && button("Back to review", "draft", "border-line text-ink-soft hover:text-ink")}
        {q.status !== "retired"
          ? button("Retire", "retired", "border-line text-ink-faint hover:text-contested")
          : button("Restore", "draft", "border-line text-ink hover:border-line-strong")}
      </div>
    </article>
  );
}
