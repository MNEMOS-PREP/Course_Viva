/**
 * A branch at a campus: Semester 1 to 8 and its electives, from one curriculum.
 *
 * All eight semesters are always tabs, because that is how a student counts.
 * A semester the curriculum PDF had no readable table for says so and links the
 * PDF, rather than quietly vanishing from the row.
 */

import { Link, useParams, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorNote, Icon, PageHeader, SkeletonRows } from "@ai/core";

import { useCampus, useProgramme, useTree } from "../api";
import type { CourseRow, ProgrammeView } from "../types";
import { Pill, ROOT, Trail, paths, plural } from "../ui/bits";

const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8];

export function ProgrammePage() {
  const { campusId = "", programmeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const year = Number(params.get("year")) || undefined;
  const programme = useProgramme(programmeId, year);
  const campus = useCampus(campusId);
  const tree = useTree();
  const view = programme.data;
  const university = tree.data?.institution?.display ?? "Amrita University";

  const trail = (
    <Trail
      items={[
        { label: university, to: ROOT },
        { label: campus.data?.campus.name ?? campusId, to: paths.campus(campusId) },
        { label: view?.programme.short ?? "…" },
      ]}
    />
  );

  if (programme.isError) {
    return (
      <>
        {trail}
        <EmptyState title="No such branch" icon="layers">
          <Link to={paths.campus(campusId)} className="text-brand hover:underline">
            Back to the campus
          </Link>
        </EmptyState>
      </>
    );
  }
  if (!view) {
    return (
      <>
        {trail}
        <SkeletonRows label="Loading the semesters" rows={8} />
      </>
    );
  }

  const tabs = [
    ...SEMESTERS.map((n) => ({ key: String(n), label: `Semester ${n}` })),
    ...(view.electives.length ? [{ key: "electives", label: "Electives" }] : []),
  ];
  const filled = view.semesters.map((s) => String(s.number));
  const chosen = params.get("sem") ?? filled[0] ?? "1";
  const runsHere = view.campuses.some((c) => c.id === campusId);

  function choose(key: string) {
    const next = new URLSearchParams(params);
    next.set("sem", key);
    setParams(next, { replace: true });
  }

  return (
    <div className="space-y-6">
      <div>
        {trail}
        <PageHeader
          eyebrow={`${view.programme.degree} · ${view.programme.school}`}
          title={view.programme.name}
          subtitle={`Runs at ${view.campuses.map((c) => c.name).join(", ")}.`}
          actions={<YearSwitch view={view} onYear={(y) => setParams(y ? { year: String(y) } : {})} />}
        />
      </div>

      {!runsHere && (
        <ErrorNote
          message={`${campus.data?.campus.name ?? "This campus"} is not listed as running this branch.`}
        />
      )}

      {view.curriculum?.status !== "parsed" ? (
        <NotRead view={view} />
      ) : (
        <>
          <div role="tablist" aria-label="Semester" className="flex flex-wrap gap-1 border-b border-line">
            {tabs.map((tab) => {
              const count =
                tab.key === "electives"
                  ? view.electives.reduce((n, b) => n + b.courses.length, 0)
                  : (view.semesters.find((s) => String(s.number) === tab.key)?.courses.length ?? 0);
              const on = tab.key === chosen;
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  onClick={() => choose(tab.key)}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors ${
                    on
                      ? "border-brand font-medium text-ink"
                      : count
                        ? "border-transparent text-ink-soft hover:text-ink"
                        : "border-transparent text-ink-faint"
                  }`}
                >
                  {tab.label}
                  <span className="ml-1.5 text-xs text-ink-faint" data-numeric>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {chosen === "electives" ? (
            view.electives.map((basket) => (
              <section key={basket.name} aria-label={basket.name}>
                <h2 className="mb-2 font-semibold text-ink">{basket.name}</h2>
                <CourseTable rows={basket.courses} campusId={campusId} view={view} />
              </section>
            ))
          ) : (
            <SemesterBody view={view} sem={Number(chosen)} campusId={campusId} />
          )}
        </>
      )}
    </div>
  );
}

function YearSwitch({ view, onYear }: { view: ProgrammeView; onYear: (y?: number) => void }) {
  if (view.curricula.length < 2) {
    return view.curriculum ? <Pill>{view.curriculum.year} curriculum</Pill> : null;
  }
  return (
    <label className="flex items-center gap-2 text-sm text-ink-soft">
      Curriculum
      <select
        value={view.curriculum?.year ?? ""}
        onChange={(e) => onYear(Number(e.target.value) || undefined)}
        className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm text-ink"
      >
        {view.curricula.map((c) => (
          <option key={c.id} value={c.year}>
            {c.year}
            {c.status === "parsed" ? "" : " (not read)"}
          </option>
        ))}
      </select>
    </label>
  );
}

function Documents({ view }: { view: ProgrammeView }) {
  const docs = view.curriculum?.documents ?? [];
  if (!docs.length) return null;
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {docs.map((d) => (
        <li key={d.url}>
          <a href={d.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand hover:underline">
            <Icon name="document" size={14} />
            {d.label}
          </a>
        </li>
      ))}
    </ul>
  );
}

function NotRead({ view }: { view: ProgrammeView }) {
  return (
    <EmptyState title="This curriculum's courses are not read yet" icon="document">
      <p>
        The {view.curriculum?.year ?? ""} curriculum is listed on amrita.edu, but its PDF has no
        table the library could read. Its documents are below; the courses appear here once it is
        read.
      </p>
      <div className="mt-3 flex justify-center">
        <Documents view={view} />
      </div>
    </EmptyState>
  );
}

function SemesterBody({ view, sem, campusId }: { view: ProgrammeView; sem: number; campusId: string }) {
  const semester = view.semesters.find((s) => s.number === sem);
  if (!semester) {
    return (
      <div className="space-y-3">
        <p className="rounded-xl border border-dashed border-line-strong bg-surface px-5 py-6 text-sm text-ink-soft">
          The {view.curriculum?.year} curriculum PDF has no course table the library could read for
          semester {sem}. If the PDF lists courses for it, they are still to be read.
        </p>
        <Documents view={view} />
      </div>
    );
  }
  const credits = semester.courses.reduce((n, c) => n + (Number(c.credits) || 0), 0);
  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-soft" data-numeric>
        {plural(semester.courses.length, "course")}
        {credits > 0 && ` · ${credits} credits`}
      </p>
      <CourseTable rows={semester.courses} campusId={campusId} view={view} />
      <Documents view={view} />
    </div>
  );
}

function CourseTable({
  rows,
  campusId,
  view,
}: {
  rows: CourseRow[];
  campusId: string;
  view: ProgrammeView;
}) {
  const year = view.curriculum?.year ?? 0;
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface">
      <table className="w-full text-sm">
        <thead className="bg-surface-sunken text-left text-xs text-ink-faint">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Code</th>
            <th scope="col" className="px-4 py-2 font-medium">Course</th>
            <th scope="col" className="px-4 py-2 font-medium">L-T-P</th>
            <th scope="col" className="px-4 py-2 font-medium">Credits</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Material</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((c) => (
            <tr key={c.id} className="transition-colors hover:bg-surface-sunken">
              <td className="code px-4 py-2.5 text-ink-soft">{c.code}</td>
              <td className="px-4 py-2.5">
                <Link to={paths.course(campusId, view.programme.id, year, c.code)} className="font-medium text-ink hover:text-brand">
                  {c.title}
                </Link>
                {!c.has_syllabus && (
                  <span className="ml-2 text-xs text-ink-faint" title="The curriculum PDF had no syllabus page for this course.">
                    no syllabus
                  </span>
                )}
              </td>
              <td className="code px-4 py-2.5 text-ink-soft">{c.ltp ?? "—"}</td>
              <td className="px-4 py-2.5 text-ink-soft" data-numeric>{c.credits ?? "—"}</td>
              <td className="px-4 py-2.5 text-right" data-numeric>
                {c.materials > 0 ? (
                  <Pill tone="confirmed">{c.materials}</Pill>
                ) : (
                  <span className="text-xs text-ink-faint">none yet</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
