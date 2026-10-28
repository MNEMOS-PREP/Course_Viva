/**
 * "Start a viva" on a course (FR-20.13): the whole course, one unit or lab,
 * one document — or ten pages of a long one — and before anything starts,
 * what the questions will be drawn from and what cannot be used (a scan has
 * no text to ask from).
 *
 * A long document is taken ten pages at a time, the way an examiner takes a
 * long subject in sittings: the next ten pages are prepared while the
 * student answers these, and the panel shows which parts are done, which are
 * ready, and which pages are only pictures.
 */

import { type ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Icon, InterviewerPhoto, SkeletonRows, prepareLines, useSession } from "@ai/core";

import { plural } from "../ui/bits";
import { useStartViva, useVivaScope } from "../vivaApi";
import type { VivaPart, VivaScope } from "../vivaTypes";
import { pagesLabel } from "./NextPart";

type Pick =
  | { kind: "all" }
  | { kind: "unit"; unit: string }
  | { kind: "material"; id: string }
  | { kind: "part"; id: string; first: number; last: number };

type Material = VivaScope["materials"][number];

const LENGTHS = [3, 6, 9, 12];

/** The part to start on: the first not done that has something to ask. */
function firstPart(m: Material): Pick {
  const part =
    m.parts.find((p) => !p.done && p.pages_with_text > 0) ??
    m.parts.find((p) => p.pages_with_text > 0) ??
    m.parts[0]!;
  return { kind: "part", id: m.id, first: part.first, last: part.last };
}

export function VivaStart({ courseId }: { courseId: string }) {
  const session = useSession();
  const scope = useVivaScope(courseId);
  const start = useStartViva();
  const navigate = useNavigate();
  const [chosen, setPick] = useState<Pick | null>(null);
  const [length, setLength] = useState(6);
  // Spoken by default: a viva is said, not written. Typing is there for a
  // library, and the room switches either way mid-viva.
  const [mode, setMode] = useState<"spoken" | "typed">("spoken");
  /** null: a lab viva when everything chosen is a lab manual. */
  const [labChoice, setLab] = useState<boolean | null>(null);

  // The examiner's opening, made by M11 while the student chooses: on the
  // CPU the greeting and warm-up took ~20 s to say, made as they were said.
  // The words naming the scope are all that is left to make in the room.
  const examiner = scope.data?.examiner;
  const sayFirst = scope.data?.say_first.join("\n");
  useEffect(() => {
    if (!examiner || !sayFirst) return;
    void prepareLines(
      sayFirst.split("\n").map((text, i) => ({
        id: `viva-opening-${examiner.id}-${i}`,
        parts: [{ text, personaId: examiner.id, voiceId: examiner.voice_id }],
      })),
      "warm",
    ).catch(() => undefined);
  }, [examiner, sayFirst]);

  const frame = (body: ReactNode) => (
    <section aria-labelledby="viva-start" className="rounded-xl border border-brand-line bg-surface p-5">
      <h2 id="viva-start" className="flex items-center gap-2 font-semibold text-ink">
        <Icon name="mic" size={16} className="text-brand" />
        Practise a viva
      </h2>
      {body}
    </section>
  );

  if (scope.isPending) return frame(<SkeletonRows label="Reading what you can be asked about" rows={2} className="mt-3" />);
  if (scope.isError) return frame(<p className="mt-2 text-sm text-contested">{scope.error.message}</p>);

  const s = scope.data;
  const excluded = s.excluded.length > 0 && (
    <ul className="mt-3 space-y-1 text-xs text-ink-faint">
      {s.excluded.map((e) => (
        <li key={e.material_id}>
          Not used: <span className="text-ink-soft">{e.title}</span> — {e.why}
        </li>
      ))}
    </ul>
  );

  if (!s.ready) {
    return frame(
      <>
        <p className="mt-2 text-sm text-ink-soft">
          An examiner asks only about what your material says, so a viva needs notes, slides or a
          lab manual with text in it. Add one here and you can be examined on it straight away.
        </p>
        {excluded}
      </>,
    );
  }

  const materials = s.materials;
  const long = materials.filter((m) => m.parts.length > 0);
  // One long document and nothing else: ten pages at a time is the way in.
  const pick: Pick = chosen ?? (materials.length === 1 && long.length === 1 ? firstPart(long[0]!) : { kind: "all" });
  const picked =
    pick.kind === "all"
      ? materials
      : pick.kind === "unit"
        ? materials.filter((m) => m.unit === pick.unit)
        : materials.filter((m) => m.id === pick.id);
  const part =
    pick.kind === "part" ? picked[0]?.parts.find((p) => p.first === pick.first) : undefined;
  const pages = part ? part.pages_with_text : picked.reduce((n, m) => n + m.usable_pages, 0);
  const hasLab = picked.some((m) => m.kind === "lab_manual");
  const lab = hasLab && (labChoice ?? picked.every((m) => m.kind === "lab_manual"));

  const begin = () =>
    start.mutate(
      {
        course_id: courseId,
        questions: length,
        mode,
        style: lab ? "lab" : "course",
        ...(pick.kind === "unit" ? { unit: pick.unit } : {}),
        ...(pick.kind === "material" ? { material_ids: [pick.id] } : {}),
        ...(pick.kind === "part"
          ? { material_ids: [pick.id], pages: { [pick.id]: [pick.first, pick.last] as [number, number] } }
          : {}),
      },
      { onSuccess: (state) => navigate(`/viva/${state.id}`) },
    );

  const option = (
    key: string,
    checked: boolean,
    onChange: () => void,
    label: ReactNode,
    disabled = false,
  ) => (
    <label
      key={key}
      className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-surface-sunken"
      }`}
    >
      <input
        type="radio"
        name="viva-scope"
        checked={checked}
        disabled={disabled}
        onChange={onChange}
        className="mt-1 accent-brand"
      />
      <span className="min-w-0 flex-1 text-sm text-ink">{label}</span>
    </label>
  );

  return frame(
    <>
      <p className="mt-1.5 text-sm text-ink-soft">
        An examiner you can see and hear asks about your material — quick one-line questions and
        ones you have to explain — and helps when you are stuck. Every question comes from a page
        you can reread afterwards.
      </p>
      <div className="mt-3 flex items-center gap-3 rounded-lg bg-surface-sunken px-3 py-2">
        <InterviewerPhoto persona={s.examiner.id} name={s.examiner.name} size={40} />
        <p className="min-w-0 text-sm leading-snug">
          <span className="block font-medium text-ink">{s.examiner.name}</span>
          <span className="block truncate text-xs text-ink-faint">
            {s.examiner.title} · your examiner this time
          </span>
        </p>
      </div>
      <fieldset className="mt-4">
        <legend className="eyebrow mb-1">Examine me on</legend>
        {option("all", pick.kind === "all", () => setPick({ kind: "all" }), "Everything here")}
        {s.units.map((unit) =>
          option(`u:${unit}`, pick.kind === "unit" && pick.unit === unit, () => setPick({ kind: "unit", unit }), unit),
        )}
        {materials.length > 1 &&
          materials.map((m) =>
            option(
              `m:${m.id}`,
              pick.kind === "material" && pick.id === m.id,
              () => setPick({ kind: "material", id: m.id }),
              <>
                {m.title} <span className="text-ink-faint">· {plural(m.usable_pages, "page")}</span>
              </>,
            ),
          )}
        {long.map((m) => (
          <div key={`parts:${m.id}`} className="mt-2">
            <p className="px-2 pb-1 text-xs text-ink-faint">
              <span className="text-ink-soft">{m.title}</span> · {plural(m.pages, "page")}, ten at a
              time
            </p>
            <div className="max-h-64 overflow-y-auto">
              {m.parts.map((p) =>
                option(
                  `p:${m.id}:${p.first}`,
                  pick.kind === "part" && pick.id === m.id && pick.first === p.first,
                  () => setPick({ kind: "part", id: m.id, first: p.first, last: p.last }),
                  <PartLabel part={p} />,
                  p.pages_with_text === 0,
                ),
              )}
            </div>
          </div>
        ))}
      </fieldset>
      {hasLab && (
        <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-sunken">
          <input
            type="checkbox"
            checked={lab}
            onChange={(e) => setLab(e.target.checked)}
            className="mt-1 accent-brand"
          />
          <span className="text-sm text-ink">
            Lab viva
            <span className="block text-xs text-ink-faint">
              The experiment in a lab examiner's order: its aim, principle, procedure,
              observations, result, precautions and sources of error.
            </span>
          </span>
        </label>
      )}
      <fieldset className="mt-3">
        <legend className="eyebrow mb-1">Answer by</legend>
        <div role="group" className="grid grid-cols-2 gap-1 rounded-lg border border-line p-0.5">
          {(
            [
              ["spoken", "Speaking", "mic"],
              ["typed", "Typing", "keyboard"],
            ] as const
          ).map(([value, label, icon]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
              className={`inline-flex items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium ${
                mode === value ? "bg-brand-soft text-brand" : "text-ink-soft hover:text-ink"
              }`}
            >
              <Icon name={icon} size={14} />
              {label}
            </button>
          ))}
        </div>
      </fieldset>
      <label className="mt-3 flex items-center justify-between gap-3 text-sm text-ink">
        Questions
        <select
          value={length}
          onChange={(e) => setLength(Number(e.target.value))}
          className="rounded-md border border-line bg-surface px-2 py-1 text-sm"
        >
          {LENGTHS.map((n) => (
            <option key={n} value={n}>
              {n} · about {n * 2} min
            </option>
          ))}
        </select>
      </label>
      <p className="mt-2 text-xs text-ink-faint" data-numeric>
        Drawn from {plural(pages, "page")}
        {part ? ` (${pagesLabel(part.first, part.last)})` : ""}.
        {part && !part.ready && part.pages_with_text > 0 && " Its questions are prepared during the warm-up."}
      </p>
      <button
        type="button"
        onClick={begin}
        disabled={start.isPending || !session || pages === 0}
        className="mt-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-brand text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
      >
        {start.isPending ? "Getting the examiner ready…" : lab ? "Start the lab viva" : "Start the viva"}
      </button>
      {!session && <p className="mt-2 text-xs text-ink-faint">Sign in to take a viva.</p>}
      {start.error && <p className="mt-2 text-xs text-contested">{start.error.message}</p>}
      {excluded}
    </>,
  );
}

/** "Pages 11–20 · done" — what a part holds, and where the student is with it. */
function PartLabel({ part }: { part: VivaPart }) {
  const pictures = part.picture_pages.length;
  return (
    <span className="flex flex-wrap items-baseline gap-x-2" data-numeric>
      <span>{pagesLabel(part.first, part.last).replace(/^p/, "P")}</span>
      {part.pages_with_text === 0 ? (
        <span className="text-xs text-ink-faint">titles and pictures only — nothing to ask</span>
      ) : (
        <>
          {part.done && <span className="text-xs font-medium text-confirmed">done</span>}
          {!part.done && part.ready && <span className="text-xs text-brand">ready</span>}
          {pictures > 0 && (
            <span className="text-xs text-ink-faint" title={`Pages ${part.picture_pages.join(", ")}`}>
              {plural(pictures, "picture")}
            </span>
          )}
        </>
      )}
    </span>
  );
}
