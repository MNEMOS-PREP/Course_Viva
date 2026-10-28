/**
 * Your progress (the user, 2026-10-29: "only when students see their progress
 * bar and strengths and weaknesses can they improve and make efforts").
 *
 * Every number here is one the vivas already measured (progress.py): how
 * often an answer was right first time, whether explanations gave a reason,
 * whether answers used the course's words and opened with the answer; fillers,
 * hesitations, the wait before answering, pace, unfinished answers. Each is
 * shown now, against where it started and the band it is in, with a line
 * over the vivas and what to do when it is worth work. Visual skills are not
 * measured yet, and the page says so rather than drawing a zero.
 *
 * Forms (dataviz): one hero figure; a stat tile per measure — a meter against
 * its target and a sparkline over vivas (one grey series, the latest viva in
 * the accent); thin single-hue bars by kind of question. Status colours carry
 * a label every time. Every value is also in the table at the foot.
 */

import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorNote, Icon, PageHeader, SkeletonRows } from "@ai/core";

import { useVivaProgress } from "../vivaApi";
import type { ProgressGroup, ProgressMeasure, VivaProgress as Progress } from "../vivaTypes";

const BAND: Record<"good" | "fair" | "work", { label: string; fill: string; track: string; text: string; icon: "check" | "info" | "alert" }> = {
  good: { label: "Good", fill: "bg-confirmed", track: "bg-confirmed-soft", text: "text-confirmed", icon: "check" },
  fair: { label: "Fair", fill: "bg-reported", track: "bg-reported-soft", text: "text-reported", icon: "info" },
  work: { label: "Worth work", fill: "bg-contested", track: "bg-contested-soft", text: "text-contested", icon: "alert" },
};

/** A measure's value, as a person reads it. */
export function shown(unit: ProgressMeasure["unit"], value: number | null): string {
  if (value === null) return "—";
  switch (unit) {
    case "share":
      return `${Math.round(value * 100)}%`;
    case "ms":
      return `${(value / 1000).toFixed(1)} s`;
    case "wpm":
      return `${Math.round(value)}`;
    default:
      return `${Math.round(value * 10) / 10}`;
  }
}

/** What "good" is, in words: "aim for 70% or more", "aim for 110–160". */
function aim(m: ProgressMeasure): string {
  if (m.better === "higher") return `aim for ${shown(m.unit, m.good)} or more`;
  if (m.better === "lower") return `aim for ${shown(m.unit, m.good)} or less`;
  return `aim for ${shown(m.unit, m.good)}–${shown(m.unit, m.good_high)}`;
}

export function VivaProgress() {
  const progress = useVivaProgress();
  if (progress.isPending) return <SkeletonRows label="Putting your progress together" rows={6} />;
  if (progress.isError) {
    return <ErrorNote message="Your progress did not load." detail={progress.error.message} onRetry={() => progress.refetch()} />;
  }
  const p = progress.data;
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader
        title="Your progress"
        subtitle={
          p.vivas
            ? `From ${p.vivas} ${p.vivas === 1 ? "viva" : "vivas"} and ${p.answers} answers: how you answer, how you speak, and where effort pays.`
            : "How you answer and how you speak, viva by viva."
        }
      />
      {p.vivas === 0 ? (
        <EmptyState
          title="Nothing to show yet"
          icon="chart"
          action={
            <Link to="/viva" className="inline-flex h-9 items-center rounded-lg bg-brand px-3.5 text-sm font-semibold text-on-brand">
              Your vivas
            </Link>
          }
        >
          Your progress builds from your first viva: every answer adds to it.
        </EmptyState>
      ) : (
        <ProgressView p={p} />
      )}
    </div>
  );
}

function ProgressView({ p }: { p: Progress }) {
  const byKey = Object.fromEntries(p.measures.map((m) => [m.key, m]));
  const hero = byKey["right_first_time"]!;
  const answering = p.measures.filter((m) => m.group !== "speaking" && m.key !== "right_first_time");
  const speaking = p.measures.filter((m) => m.group === "speaking");
  return (
    <>
      <Hero m={hero} vivas={p.vivas} />

      <div className="grid gap-4 md:grid-cols-2">
        <Notes title="Strengths" empty="Your strengths show here once a measure is in its good band." notes={p.strengths} />
        <Notes title="Worth working on" empty="Nothing stands out to work on: keep it up." notes={p.work_on} tips />
      </div>

      <Section title="How you answer" sub="What you say: whether it is right, explained and put together well.">
        {answering.map((m) => (
          <Tile key={m.key} m={m} labels={p.series} />
        ))}
      </Section>

      <Section title="How you speak" sub="How it sounds: pace on answers spoken aloud, the rest on every answer.">
        {speaking.map((m) => (
          <Tile key={m.key} m={m} labels={p.series} />
        ))}
      </Section>

      <Kinds groups={p.by_family} lengths={p.by_length} />

      <Visual visual={p.visual} />

      <Table p={p} />
    </>
  );
}

function Hero({ m, vivas }: { m: ProgressMeasure; vivas: number }) {
  return (
    <section aria-labelledby="hero" className="rounded-xl border border-line bg-surface p-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <h2 id="hero" className="text-sm font-medium text-ink-soft">
            {m.label}
          </h2>
          <p className="mt-1 text-5xl font-semibold tracking-tight text-ink">{shown(m.unit, m.now)}</p>
          <p className="mt-2 text-sm text-ink-soft">
            {m.means} <Delta m={m} vivas={vivas} />
          </p>
        </div>
        <Sparkline m={m} labels={null} wide />
      </div>
      <Meter m={m} />
    </section>
  );
}

function Delta({ m, vivas }: { m: ProgressMeasure; vivas: number }) {
  if (m.first === null || m.direction === null) {
    return (
      <span className="text-ink-faint">
        {vivas < 4 ? "Which way it is moving shows after four vivas." : ""}
      </span>
    );
  }
  const tone = m.direction === "better" ? "text-confirmed" : m.direction === "worse" ? "text-contested" : "text-ink-soft";
  return (
    <span className={`font-medium ${tone}`}>
      {m.direction === "steady" ? "Steady" : m.direction === "better" ? "Better" : "Worse"} than your first vivas (
      {shown(m.unit, m.first)}).
    </span>
  );
}

function Section({ title, sub, children }: { title: string; sub: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3">
      <div>
        <h2 className="font-semibold text-ink">{title}</h2>
        <p className="text-sm text-ink-soft">{sub}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
    </section>
  );
}

function Tile({ m, labels }: { m: ProgressMeasure; labels: Progress["series"] }) {
  const band = m.band ? BAND[m.band] : null;
  return (
    <article className="flex flex-col rounded-xl border border-line bg-surface p-4" aria-label={m.label}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-ink-soft">{m.label}</h3>
        {band && (
          <span className={`inline-flex shrink-0 items-center gap-1 text-xs font-medium ${band.text}`}>
            <Icon name={band.icon} size={12} />
            {band.label}
          </span>
        )}
      </div>
      <div className="mt-1 flex items-end justify-between gap-3">
        <p className="text-2xl font-semibold tracking-tight text-ink">
          {m.now === null ? <span className="text-base font-normal text-ink-faint">not measured yet</span> : shown(m.unit, m.now)}
        </p>
        <Sparkline m={m} labels={labels} />
      </div>
      <Meter m={m} />
      <p className="mt-2 text-xs text-ink-faint">{m.means}</p>
      {m.band === "work" && <p className="mt-2 text-xs text-ink">{m.tip}</p>}
    </article>
  );
}

/** The scale a meter is drawn on: the target and the value both fit. */
function scale(m: ProgressMeasure): [number, number] {
  if (m.unit === "share") return [0, 1];
  const top = Math.max(m.now ?? 0, m.fair_high ?? m.fair, m.good_high ?? m.good) * 1.25;
  return [0, top || 1];
}

function Meter({ m }: { m: ProgressMeasure }) {
  const [low, high] = scale(m);
  const at = (v: number) => `${Math.max(0, Math.min(100, ((v - low) / (high - low)) * 100))}%`;
  const band = m.band ? BAND[m.band] : null;
  const target = m.better === "band" ? [m.good, m.good_high ?? m.good] : [m.good];
  return (
    <div className="mt-3">
      <div className={`relative h-2 rounded-full ${band ? band.track : "bg-surface-sunken"}`}>
        {m.now !== null && band && (
          <div className={`absolute inset-y-0 left-0 rounded-full ${band.fill}`} style={{ width: at(m.now) }} />
        )}
        {target.map((t, i) => (
          <span
            key={i}
            aria-hidden
            className="absolute -top-1 h-4 w-px bg-ink-soft"
            style={{ left: at(t) }}
          />
        ))}
      </div>
      <p className="mt-1 text-[11px] text-ink-faint">{aim(m)}</p>
    </div>
  );
}

/** One series over the vivas: grey line, the latest viva in the accent. */
function Sparkline({ m, labels, wide = false }: { m: ProgressMeasure; labels: Progress["series"] | null; wide?: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  const points = m.series.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v !== null);
  if (points.length < 2) return null;
  const w = wide ? 220 : 96;
  const h = wide ? 56 : 32;
  const pad = 5;
  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const x = (i: number) => pad + (i / Math.max(1, m.series.length - 1)) * (w - 2 * pad);
  const y = (v: number) => (max === min ? h / 2 : pad + (1 - (v - min) / (max - min)) * (h - 2 * pad));
  const path = points.map((p, k) => `${k ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const last = points[points.length - 1]!;
  const shownPoint = hover !== null ? points.find((p) => p.i === hover) : null;
  return (
    <div className="relative shrink-0" style={{ width: w, height: h }}>
      <svg
        width={w}
        height={h}
        role="img"
        aria-label={`${m.label} over ${points.length} vivas: from ${shown(m.unit, points[0]!.v)} to ${shown(m.unit, last.v)}`}
        onMouseLeave={() => setHover(null)}
      >
        <path d={path} fill="none" className="stroke-ink-faint" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(last.i)} cy={y(last.v)} r={4} className="fill-brand stroke-surface" strokeWidth={2} />
        {points.map((p) => (
          <rect
            key={p.i}
            x={x(p.i) - 12}
            y={0}
            width={24}
            height={h}
            fill="transparent"
            onMouseEnter={() => setHover(p.i)}
          />
        ))}
        {shownPoint && <circle cx={x(shownPoint.i)} cy={y(shownPoint.v)} r={4} className="fill-ink stroke-surface" strokeWidth={2} />}
      </svg>
      {shownPoint && (
        <div className="pointer-events-none absolute bottom-full right-0 z-10 mb-1 whitespace-nowrap rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink shadow-sm">
          <span className="font-medium">{shown(m.unit, shownPoint.v)}</span>
          <span className="text-ink-faint">
            {" "}
            · viva {shownPoint.i + 1}
            {labels?.[shownPoint.i] ? `, ${new Date(labels[shownPoint.i]!.date).toLocaleDateString()}` : ""}
          </span>
        </div>
      )}
    </div>
  );
}

function Notes({ title, notes, empty, tips = false }: { title: string; notes: Progress["strengths"]; empty: string; tips?: boolean }) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5" aria-label={title}>
      <h2 className="mb-3 font-semibold text-ink">{title}</h2>
      {notes.length ? (
        <ul className="space-y-2.5 text-sm">
          {notes.map((n) => (
            <li key={`${n.kind}:${n.key}`}>
              <span className="text-ink">{n.text}</span>
              {tips && n.tip && <span className="mt-0.5 block text-xs text-ink-soft">{n.tip}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-soft">{empty}</p>
      )}
    </section>
  );
}

/** Right first time, by kind of question: one hue, magnitude. */
function Kinds({ groups, lengths }: { groups: ProgressGroup[]; lengths: ProgressGroup[] }) {
  const rows = [...lengths, ...groups];
  if (!rows.length) return null;
  return (
    <section aria-labelledby="kinds" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="kinds" className="font-semibold text-ink">
        Right first time, by kind of question
      </h2>
      <p className="text-sm text-ink-soft">Where you are sure, and where the marks go.</p>
      <dl className="mt-4 space-y-2.5">
        {rows.map((g, i) => (
          <div key={`${i < lengths.length ? "l" : "f"}:${g.key}`} className={`grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] items-center gap-3 ${i === lengths.length ? "border-t border-line pt-3" : ""}`}>
            <dt className="truncate text-sm text-ink" title={g.label}>
              {g.label}
            </dt>
            <dd className="flex items-center gap-2">
              <span className="relative h-3 flex-1 rounded-sm bg-surface-sunken">
                <span className="absolute inset-y-0 left-0 rounded-r bg-brand" style={{ width: `${Math.max(2, g.share * 100)}%` }} />
              </span>
              <span className="w-24 shrink-0 text-right text-xs text-ink-soft" data-numeric>
                {g.right} of {g.asked} · {Math.round(g.share * 100)}%
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Visual({ visual }: { visual: Progress["visual"] }) {
  return (
    <section aria-labelledby="visual" className="rounded-xl border border-dashed border-line bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="visual" className="font-semibold text-ink">
          How you come across
        </h2>
        <span className="rounded-full border border-line bg-surface-sunken px-2 py-0.5 text-xs text-ink-soft">
          not measured yet
        </span>
      </div>
      <p className="mt-1 text-sm text-ink-soft">{visual.note}</p>
      <ul className="mt-3 flex flex-wrap gap-2">
        {visual.planned.map((item) => (
          <li key={item} className="rounded-lg border border-line px-3 py-1.5 text-sm text-ink-faint">
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Every value, viva by viva: the table twin of every chart above. */
function Table({ p }: { p: Progress }) {
  return (
    <details className="rounded-xl border border-line bg-surface p-5">
      <summary className="cursor-pointer text-sm font-medium text-ink">See every number, viva by viva</summary>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs" data-numeric>
          <thead>
            <tr className="border-b border-line text-ink-soft">
              <th className="py-2 pr-3 font-medium">Viva</th>
              {p.measures.map((m) => (
                <th key={m.key} className="px-2 py-2 font-medium">
                  {m.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.series.map((v, i) => (
              <tr key={v.id} className="border-b border-line last:border-0">
                <td className="py-2 pr-3 text-ink">
                  <Link to={`/viva/${v.id}/report`} className="hover:underline">
                    {new Date(v.date).toLocaleDateString()} · {v.label}
                  </Link>
                </td>
                {p.measures.map((m) => (
                  <td key={m.key} className="px-2 py-2 text-ink-soft">
                    {shown(m.unit, m.series[i] ?? null)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
