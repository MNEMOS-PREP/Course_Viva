/**
 * "Start a viva" on a course (FR-20.13): the whole course, one unit or lab,
 * or one document — and before anything starts, what the questions will be
 * drawn from and what cannot be used (a scan has no text to ask from).
 */

import { type ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Icon, SkeletonRows, useSession } from "@ai/core";

import { plural } from "../ui/bits";
import { useStartViva, useVivaScope } from "../vivaApi";

type Pick = { kind: "all" } | { kind: "unit"; unit: string } | { kind: "material"; id: string };

const LENGTHS = [3, 6, 9, 12];

export function VivaStart({ courseId }: { courseId: string }) {
  const session = useSession();
  const scope = useVivaScope(courseId);
  const start = useStartViva();
  const navigate = useNavigate();
  const [pick, setPick] = useState<Pick>({ kind: "all" });
  const [length, setLength] = useState(6);
  // Spoken by default: a viva is said, not written. Typing is there for a
  // library, and the room switches either way mid-viva.
  const [mode, setMode] = useState<"spoken" | "typed">("spoken");

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
  const pages =
    pick.kind === "all"
      ? materials.reduce((n, m) => n + m.usable_pages, 0)
      : pick.kind === "unit"
        ? materials.filter((m) => m.unit === pick.unit).reduce((n, m) => n + m.usable_pages, 0)
        : (materials.find((m) => m.id === pick.id)?.usable_pages ?? 0);

  const begin = () =>
    start.mutate(
      {
        course_id: courseId,
        questions: length,
        mode,
        ...(pick.kind === "unit" ? { unit: pick.unit } : {}),
        ...(pick.kind === "material" ? { material_ids: [pick.id] } : {}),
      },
      { onSuccess: (state) => navigate(`/viva/${state.id}`) },
    );

  const option = (key: string, checked: boolean, onChange: () => void, label: ReactNode) => (
    <label key={key} className="flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-sunken">
      <input type="radio" name="viva-scope" checked={checked} onChange={onChange} className="mt-1 accent-brand" />
      <span className="text-sm text-ink">{label}</span>
    </label>
  );

  return frame(
    <>
      <p className="mt-1.5 text-sm text-ink-soft">
        An examiner you can see and hear asks about your material — quick one-line questions and
        ones you have to explain — and helps when you are stuck. Every question comes from a page
        you can reread afterwards.
      </p>
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
      </fieldset>
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
        Drawn from {plural(pages, "page")}.
      </p>
      <button
        type="button"
        onClick={begin}
        disabled={start.isPending || !session || pages === 0}
        className="mt-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-brand text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
      >
        {start.isPending ? "Getting the examiner ready…" : "Start the viva"}
      </button>
      {!session && <p className="mt-2 text-xs text-ink-faint">Sign in to take a viva.</p>}
      {start.error && <p className="mt-2 text-xs text-contested">{start.error.message}</p>}
      {excluded}
    </>,
  );
}
