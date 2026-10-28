/**
 * The viva's report (FR-20.18): what you knew, what to read again — by page —
 * and how you sounded, with the trend over your last vivas.
 *
 * Counts and measures, never a score: a mark out of ten from a practice viva
 * is the number a student remembers and the one least worth trusting.
 */

import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { EmptyState, Icon, SkeletonRows } from "@ai/core";

import { openFile } from "../api";
import { plural } from "../ui/bits";
import { HELP_LABEL, VERDICT, VERDICT_ORDER, VerdictBadge } from "../ui/verdict";
import { useStartViva, useVivaReport } from "../vivaApi";
import type { LabStage, ReportItem, VivaReport as Report } from "../vivaTypes";
import { NextPart, pagesLabel, scopeLabel } from "./NextPart";

export function VivaReport() {
  const { vivaId = "" } = useParams();
  const report = useVivaReport(vivaId);
  if (report.isPending) return <SkeletonRows label="Putting your report together" rows={6} />;
  if (report.isError) {
    return (
      <EmptyState title="No such viva" icon="mic">
        <Link to="/viva" className="text-brand hover:underline">
          Your vivas
        </Link>
      </EmptyState>
    );
  }
  return <ReportView report={report.data} />;
}

function seconds(ms: number | null): string {
  if (ms === null) return "—";
  return ms < 1000 ? "under a second" : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}

function ReportView({ report }: { report: Report }) {
  const v = report.viva;
  const answered = report.items.filter((i) => i.status !== "not_answered").length;
  const shown = VERDICT_ORDER.filter((s) => report.counts[s]);
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-medium text-ink-faint">
          {v.course && <span className="code mr-2">{v.course.code}</span>}
          {scopeLabel(v.scope, v.part)} · with {v.examiner} · {new Date(v.started_at).toLocaleDateString()}
        </p>
        <h1 className="mt-1 text-title font-semibold tracking-tight text-ink">
          Your {v.retry_of ? "second-go" : v.style === "lab" ? "lab viva" : "viva"} report
        </h1>
        <p className="mt-2 text-sm text-ink-soft" data-numeric>
          {plural(answered, "question")} answered
          {v.status === "live" && " so far — the viva is still open"}
          {v.end_reason === "ended_by_student" && " — you ended it early"}.
        </p>
        {shown.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-2" aria-label="How the answers went">
            {shown.map((s) => (
              <li key={s} className="inline-flex items-center gap-1.5 text-sm text-ink-soft" data-numeric>
                <VerdictBadge status={s} size="sm" /> {report.counts[s]}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-5 flex flex-wrap gap-2">
          {v.status === "live" && (
            <Link to={`/viva/${v.id}`} className="inline-flex h-9 items-center rounded-lg bg-brand px-3.5 text-sm font-semibold text-on-brand">
              Back to the viva
            </Link>
          )}
          {v.status === "ended" && v.missed > 0 && v.course && <SecondGo report={report} />}
          <Link to="/viva" className="inline-flex h-9 items-center rounded-lg border border-line px-3.5 text-sm font-medium text-ink hover:border-line-strong">
            All your vivas
          </Link>
        </div>
      </header>

      {report.coverage && <Coverage report={report} />}

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="What you knew">
          {report.knew.length ? (
            <ul className="space-y-1.5 text-sm text-ink">
              {report.items
                .filter((i) => report.knew.includes(i.item))
                .map((i) => (
                  <li key={i.item} className="flex gap-2">
                    <span className="text-confirmed" aria-hidden>
                      ✓
                    </span>
                    {i.question}
                  </li>
                ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-soft">
              Nothing came out right first time in this one. The pages to read again are beside
              this.
            </p>
          )}
        </Panel>
        <Panel title="What to read again">
          {report.reread.length ? (
            <ul className="space-y-3">
              {report.reread.map((r) => (
                <li key={`${r.material_id}:${r.page}`}>
                  <p className="text-sm font-medium text-ink">
                    {r.title}, page {r.page}
                    <button
                      type="button"
                      onClick={() => openFile(r.material_id).catch(() => undefined)}
                      className="ml-2 text-xs font-normal text-brand hover:underline"
                    >
                      Open
                    </button>
                  </p>
                  {r.quotes.map((q) => (
                    <blockquote key={q} className="mt-1 border-l-2 border-brand-line pl-3 text-sm leading-relaxed text-ink-soft">
                      {q}
                    </blockquote>
                  ))}
                  <p className="mt-1 text-xs text-ink-faint">
                    For question {r.items.join(", ")}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-soft">Nothing — every question you answered was right first time.</p>
          )}
        </Panel>
      </div>

      <Sounded report={report} />

      <section aria-labelledby="by-question" className="space-y-3">
        <h2 id="by-question" className="font-semibold text-ink">
          Question by question
        </h2>
        {report.items.map((item) => (
          <ItemCard key={item.item} item={item} />
        ))}
        {v.skill_graph && (
          <p className="text-xs text-ink-faint">
            {v.skill_graph.sent > 0
              ? `Added to your skill graph: ${v.skill_graph.sent} ${v.skill_graph.sent === 1 ? "entry" : "entries"}, with your answers as the evidence.`
              : `Not added to your skill graph: ${v.skill_graph.why}.`}
          </p>
        )}
        {report.marked_by_rules && (
          <p className="text-xs text-ink-faint">
            Some answers were marked by matching their words to the page, because the marking model
            was not available. Those marks are rougher than usual.
          </p>
        )}
      </section>
    </div>
  );
}

/** A second go at what was not right first time, straight away, while the
 *  report is still in front of the student (NotebookLM reruns missed cards). */
function SecondGo({ report }: { report: Report }) {
  const v = report.viva;
  const start = useStartViva();
  const navigate = useNavigate();
  return (
    <>
      <button
        type="button"
        disabled={start.isPending}
        onClick={() =>
          start.mutate(
            { course_id: v.course!.id, retry_of: v.id, mode: v.mode, style: v.style },
            { onSuccess: (state) => navigate(`/viva/${state.id}`) },
          )
        }
        className="inline-flex h-9 items-center gap-2 rounded-lg bg-brand px-3.5 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
      >
        {start.isPending
          ? "Getting the examiner ready…"
          : v.missed === 1
            ? "Try the one you missed again"
            : `Try the ${v.missed} you missed again`}
      </button>
      {start.error && <p className="w-full text-xs text-contested">{start.error.message}</p>}
    </>
  );
}

/** "1, 2 and 4" */
function listed(pages: number[]): string {
  if (pages.length <= 1) return pages.join("");
  return `${pages.slice(0, -1).join(", ")} and ${pages[pages.length - 1]}`;
}

/** What this sitting covered of a long document, what it could not, and the
 *  next ten pages — so "no page lost" is something the student can see. */
function Coverage({ report }: { report: Report }) {
  const c = report.coverage!;
  const v = report.viva;
  const pictures = c.picture_pages;
  const titles = c.title_pages;
  return (
    <section aria-labelledby="coverage" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="coverage" className="font-semibold text-ink">
        {c.title}, {pagesLabel(c.first, c.last)}
      </h2>
      <p className="mt-1.5 text-sm text-ink-soft" data-numeric>
        {c.asked_from.length
          ? `The questions came from ${c.asked_from.length === 1 ? "page" : "pages"} ${listed(c.asked_from)}.`
          : "No question was asked from these pages."}{" "}
        {titles.length > 0 &&
          `${titles.length === 1 ? "Page" : "Pages"} ${listed(titles)} ${
            titles.length === 1 ? "is a title" : "are titles"
          }. `}
        {pictures.length > 0 &&
          `${pictures.length === 1 ? "Page" : "Pages"} ${listed(pictures)} ${
            pictures.length === 1 ? "is a picture" : "are pictures"
          } with no text to ask from — a diagram or an equation drawn as an image — so look at ${
            pictures.length === 1 ? "it" : "them"
          } yourself.`}
      </p>
      {report.next_part && v.course && v.status === "ended" && (
        <NextPart
          next={report.next_part}
          courseId={v.course.id}
          mode={v.mode}
          style={v.style}
          questions={v.target}
          className="mt-4"
        />
      )}
    </section>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5">
      <h2 className="mb-3 font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

function Stat({ value, label, note }: { value: ReactNode; label: string; note?: string }) {
  return (
    <div>
      <p className="text-xl font-semibold tracking-tight text-ink" data-numeric>
        {value}
      </p>
      <p className="mt-0.5 text-xs text-ink-faint">{label}</p>
      {note && <p className="mt-0.5 text-xs text-ink-soft">{note}</p>}
    </div>
  );
}

const DIRECTION: Record<"better" | "worse" | "steady", string> = {
  better: "falling",
  worse: "rising",
  steady: "about the same",
};

function Sounded({ report }: { report: Report }) {
  const s = report.sounded;
  const t = report.trend;
  return (
    <section aria-labelledby="sounded" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="sounded" className="font-semibold text-ink">
        How you {report.viva.mode === "spoken" ? "sounded" : "answered"}
      </h2>
      <div className="mt-4 grid grid-cols-2 gap-5 sm:grid-cols-4">
        <Stat
          value={s.fillers_per_100 ?? "—"}
          label="fillers per 100 words"
          note={s.top_filler ? `mostly "${s.top_filler}"` : undefined}
        />
        <Stat value={seconds(s.silence_ms_median)} label="usual wait before answering" />
        <Stat value={s.long_silences} label="waits of 8 s or more" />
        <Stat value={s.unfinished} label={s.unfinished === 1 ? "answer left unfinished" : "answers left unfinished"} />
        <Stat value={s.words_per_answer ?? "—"} label="words per answer" />
        <Stat value={s.hedges_per_100 ?? "—"} label="hesitations per 100 words" note={'"I think", "maybe", "probably"'} />
        <Stat
          value={s.direct_share === null ? "—" : `${Math.round(s.direct_share * 100)}%`}
          label="answers that start with the answer"
          note='not "um, so, well…"'
        />
        <Stat value={s.words_per_sentence ?? "—"} label="words per sentence" note={s.run_on ? `${s.run_on} ran on past 35 words` : undefined} />
        {s.cut_in > 0 && (
          <Stat value={s.cut_in} label={s.cut_in === 1 ? "answer the examiner cut short" : "answers the examiner cut short"} note="a one-line question answered at length" />
        )}
        <Stat
          value={s.wpm ?? "—"}
          label="words per minute"
          note={s.spoken_answers ? undefined : "typed — pace is measured on spoken answers"}
        />
      </div>
      {t ? (
        <p className="mt-4 border-t border-line pt-3 text-sm text-ink-soft">
          Over your last {t.vivas} vivas: fillers {t.fillers ? DIRECTION[t.fillers] : "not measured"}, waits
          before answering {t.silences ? DIRECTION[t.silences] : "not measured"}.
        </p>
      ) : (
        <p className="mt-4 border-t border-line pt-3 text-xs text-ink-faint">
          After three vivas this shows whether these are getting better.
        </p>
      )}
    </section>
  );
}

const STAGE_LABEL: Record<LabStage, string> = {
  principle: "Principle",
  procedure: "Procedure",
  observations: "Observations",
  result: "Result",
  precautions: "Precautions",
  "sources of error": "Sources of error",
  aim: "Aim",
};

function ItemCard({ item }: { item: ReportItem }) {
  const meta = VERDICT[item.status];
  return (
    <article className={`rounded-xl border border-l-4 border-line bg-surface p-5 ${meta.accent}`} aria-labelledby={`q-${item.item}`}>
      <header className="flex flex-wrap items-center gap-2">
        <VerdictBadge status={item.status} />
        {item.help.map((h) => (
          <span key={h} className="text-xs text-ink-faint">
            {HELP_LABEL[h]}
          </span>
        ))}
        <span className="ml-auto text-xs text-ink-faint">
          {item.stage && <span className="font-medium text-ink-soft">{STAGE_LABEL[item.stage]} · </span>}
          {item.answer_length === "short" ? "Short answer · " : item.answer_length === "long" ? "Long answer · " : ""}
          Question {item.item}
        </span>
      </header>
      <h3 id={`q-${item.item}`} className="mt-2 font-semibold leading-snug text-ink">
        {item.question}
      </h3>

      {item.answers.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <p className="eyebrow">{item.answers.length > 1 ? "Your answers" : "Your answer"}</p>
          {item.answers.map((a, i) => (
            <blockquote key={i} className="rounded-lg bg-brand-soft/60 px-3 py-2 text-sm leading-relaxed text-ink">
              {a.text}
            </blockquote>
          ))}
        </div>
      )}

      {item.wrong && (
        <p className="mt-3 text-sm leading-relaxed text-ink-soft">
          <span className="font-medium text-contested">What went wrong: </span>you said “{item.wrong.said}” —{" "}
          {item.wrong.why}
        </p>
      )}

      {(item.covered.length > 0 || item.missing.length > 0) && (
        <div className="mt-3">
          <p className="eyebrow mb-1">What a good answer says</p>
          <ul className="space-y-1 text-sm text-ink">
            {item.covered.map((p) => (
              <li key={p} className="flex gap-2">
                <Icon name="check" size={14} className="mt-0.5 shrink-0 text-confirmed" />
                {p}
                <span className="sr-only"> — you said this</span>
              </li>
            ))}
            {item.missing.map((p) => (
              <li key={p} className="flex gap-2">
                <span aria-hidden className="mt-0.5 w-3.5 shrink-0 text-center text-contested">
                  ✕
                </span>
                {p}
                <span className="sr-only"> — not in your answer</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.cite && (
        <div className="mt-3 rounded-lg bg-surface-sunken p-3">
          <p className="text-xs font-medium text-ink-soft">
            From page {item.cite.page} of {item.cite.title}
            {item.cite.read_from_picture && (
              <span className="font-normal text-ink-faint"> · read from the slide's picture</span>
            )}
          </p>
          <blockquote className="mt-1 text-sm leading-relaxed text-ink">{item.cite.quote}</blockquote>
        </div>
      )}

      <p className="mt-2 text-xs text-ink-faint">
        {item.written_by === "rules"
          ? "A question written by rule from the page."
          : "A question written by a model from the page, checked against it"}
        {item.written_by !== "rules" && (item.reviewed ? " and reviewed by the placement cell." : "; not yet reviewed by a person.")}
      </p>

      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-ink-faint hover:text-ink-soft">The whole exchange</summary>
        <ol className="mt-2 space-y-1.5 text-sm">
          {item.exchange.map((t, i) => (
            <li key={i} className={t.role === "student" ? "pl-6 text-ink" : "text-ink-soft"}>
              <span className="mr-1.5 text-xs text-ink-faint">{t.role === "student" ? "You" : "Examiner"}</span>
              {t.text}
            </li>
          ))}
        </ol>
      </details>
    </article>
  );
}

