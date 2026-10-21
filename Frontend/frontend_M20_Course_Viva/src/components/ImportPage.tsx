/**
 * Import a folder (FR-20.6, FR-20.7): the placement cell's fast way in.
 *
 * Download the empty tree, drop files into course folders, pick the folder
 * here. Nothing is added until the plan has been read: every file is either
 * placed in a course or told why not, and only then uploaded (AC-20.5).
 */

import { useMemo, useState } from "react";

import { Button, EmptyState, ErrorNote, PageHeader, isStaff, useSession } from "@ai/core";

import { FOLDERS_ZIP, pathOf, planImport, runImport, useRefreshLibrary } from "../api";
import type { ImportDone, ImportDryRun } from "../types";
import { KIND_LABEL, Pill, plural, sizeOf } from "../ui/bits";

export function ImportPage() {
  const session = useSession();
  const refresh = useRefreshLibrary();
  const [files, setFiles] = useState<File[]>([]);
  const [shared, setShared] = useState(true);
  const [plan, setPlan] = useState<ImportDryRun | null>(null);
  const [done, setDone] = useState<ImportDone | null>(null);
  const [progress, setProgress] = useState<{ sent: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const placed = useMemo(() => {
    if (!plan) return [];
    const wanted = new Set(plan.would_add.map((p) => p.path));
    return files.filter((f) => wanted.has(pathOf(f)));
  }, [plan, files]);
  const placedBytes = placed.reduce((n, f) => n + f.size, 0);

  if (!isStaff(session)) {
    return (
      <EmptyState title="Folder import is the placement cell's" icon="shield">
        To add material to one course, open the course and use Add material.
      </EmptyState>
    );
  }

  async function choose(list: FileList | null) {
    const chosen = Array.from(list ?? []);
    setFiles(chosen);
    setPlan(null);
    setDone(null);
    setError(null);
    if (!chosen.length) return;
    setBusy(true);
    try {
      setPlan(await planImport(chosen, shared));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The folder could not be read.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      setDone(await runImport(placed, shared, (sent, total) => setProgress({ sent, total })));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The import stopped.");
    } finally {
      setBusy(false);
    }
  }

  const byCourse = new Map<string, number>();
  for (const p of plan?.would_add ?? []) byCourse.set(p.course_id, (byCourse.get(p.course_id) ?? 0) + 1);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Import a folder"
        subtitle="Fill the folder tree with material, then bring the whole thing in at once."
        how={
          <>
            <p>
              The tree is <span className="code">Amrita University / Campus / Branch / Semester_N /
              CODE - Title /</span>, with <span className="code">Electives / Basket /</span> beside
              the semesters. A file's folder decides its course; a subfolder or file name with
              "lab", "slides", "PYQ" or "syllabus" in it decides its kind, and "Unit 3" or "Lab 6"
              its unit.
            </p>
            <p className="mt-2">
              The same file twice in a course is one material, so importing a folder again only
              adds what is new.
            </p>
          </>
        }
        actions={
          <a href={FOLDERS_ZIP} className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-ink hover:border-line-strong">
            Download the empty folder tree
          </a>
        }
      />

      <section className="space-y-4 rounded-xl border border-line bg-surface px-5 py-5">
        <div>
          <p className="mb-2 text-sm font-medium text-ink">
            Pick the "Amrita University" folder, or any campus or branch folder inside it
          </p>
          <label
            className={`inline-flex cursor-pointer items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-hover ${
              busy ? "pointer-events-none opacity-55" : ""
            }`}
          >
            Choose a folder
            <input
              ref={folderPicker}
              type="file"
              multiple
              disabled={busy}
              onChange={(e) => choose(e.target.files)}
              className="sr-only"
            />
          </label>
        </div>
        <label className="flex items-start gap-2 text-sm text-ink-soft">
          <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} disabled={busy} className="mt-0.5" />
          <span>
            Share it with every campus that teaches the course. Untick to tag each file with the
            campus folder it came from.
          </span>
        </label>
        {files.length > 0 && (
          <p className="text-sm text-ink-soft" data-numeric>
            {plural(files.length, "file")} chosen{busy && !plan ? " · reading the folder…" : ""}
          </p>
        )}
      </section>

      {error && <ErrorNote message={error} />}

      {plan && !done && (
        <section aria-labelledby="plan" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="plan" className="font-semibold text-ink">
              The plan: {plural(plan.would_add.length, "file")} into {plural(byCourse.size, "course")}
              {plan.problems.length > 0 && `, ${plural(plan.problems.length, "file")} left out`}
            </h2>
            <Button onClick={confirm} disabled={busy || !placed.length}>
              {busy && progress
                ? `Uploading ${progress.sent} of ${progress.total}…`
                : `Import ${plural(placed.length, "file")} (${sizeOf(placedBytes)})`}
            </Button>
          </div>
          {plan.problems.length > 0 && <Problems problems={plan.problems} />}
          <div className="max-h-[28rem] overflow-y-auto rounded-xl border border-line bg-surface">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-sunken text-left text-xs text-ink-faint">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">File</th>
                  <th scope="col" className="px-4 py-2 font-medium">Course</th>
                  <th scope="col" className="px-4 py-2 font-medium">Kind</th>
                  <th scope="col" className="px-4 py-2 font-medium">Unit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {plan.would_add.map((p) => (
                  <tr key={p.path}>
                    <td className="max-w-xs truncate px-4 py-2 text-ink" title={p.path}>
                      {p.path.split("/").pop()}
                    </td>
                    <td className="code px-4 py-2 text-ink-soft">{p.course_id.split(":")[1]}</td>
                    <td className="px-4 py-2 text-ink-soft">{KIND_LABEL[p.kind]}</td>
                    <td className="px-4 py-2 text-ink-soft">{p.unit ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {done && (
        <section aria-labelledby="done" className="space-y-4">
          <h2 id="done" className="font-semibold text-ink">
            Imported
          </h2>
          <div className="flex flex-wrap gap-2">
            <Pill tone="confirmed">{plural(done.added, "file")} added</Pill>
            {done.already_there > 0 && <Pill>{done.already_there} already there</Pill>}
            {done.problems.length > 0 && <Pill tone="contested">{done.problems.length} not added</Pill>}
          </div>
          {done.problems.length > 0 && <Problems problems={done.problems} />}
        </section>
      )}
    </div>
  );
}

/** React has no prop for a folder picker; the attribute is set on the element. */
function folderPicker(input: HTMLInputElement | null) {
  input?.setAttribute("webkitdirectory", "");
}

function Problems({ problems }: { problems: { path: string; reason: string }[] }) {
  return (
    <details className="rounded-xl border border-reported-line bg-reported-soft px-5 py-3 text-sm">
      <summary className="cursor-pointer font-medium text-ink">
        {plural(problems.length, "file")} left out, and why
      </summary>
      <ul className="mt-3 max-h-64 space-y-1.5 overflow-y-auto">
        {problems.map((p) => (
          <li key={p.path}>
            <span className="code text-ink">{p.path}</span>
            <span className="text-ink-soft"> — {p.reason}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
