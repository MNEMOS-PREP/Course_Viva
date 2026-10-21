/**
 * Coverage: per campus and branch, how many courses have anything to prepare
 * from (FR-20.12). The placement cell's to-do list, and honest about the gaps.
 */

import { Link } from "react-router-dom";

import { ErrorNote, PageHeader, SkeletonRows } from "@ai/core";

import { useCoverage } from "../api";
import type { CoverageRow } from "../types";
import { paths } from "../ui/bits";

export function CoveragePage() {
  const coverage = useCoverage();
  const byCampus = new Map<string, CoverageRow[]>();
  for (const row of coverage.data ?? []) {
    byCampus.set(row.campus, [...(byCampus.get(row.campus) ?? []), row]);
  }
  const total = (coverage.data ?? []).reduce((n, r) => n + r.courses, 0);
  const covered = (coverage.data ?? []).reduce((n, r) => n + r.with_material, 0);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Coverage"
        subtitle={
          coverage.data
            ? `${covered} of ${total} course listings have any material yet.`
            : "How many courses have anything to prepare from."
        }
        how={
          <p>
            A course taught at two campuses counts once at each, because a student at either
            campus is looking for it. Material added at one is seen at both.
          </p>
        }
      />
      {coverage.isPending && <SkeletonRows label="Loading coverage" rows={8} />}
      {coverage.isError && <ErrorNote message="Coverage did not load." onRetry={() => coverage.refetch()} />}

      {[...byCampus.entries()].map(([campus, rows]) => (
        <section key={campus} aria-labelledby={`cov-${campus}`}>
          <h2 id={`cov-${campus}`} className="eyebrow mb-3">
            {campus}
          </h2>
          <div className="overflow-hidden rounded-xl border border-line bg-surface">
            <table className="w-full table-fixed text-sm">
              <thead className="bg-surface-sunken text-left text-xs text-ink-faint">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Branch</th>
                  <th scope="col" className="w-28 px-4 py-2 font-medium">Curriculum</th>
                  <th scope="col" className="w-28 px-4 py-2 font-medium">Courses</th>
                  <th scope="col" className="w-72 px-4 py-2 font-medium">With material</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => {
                  const share = r.courses ? r.with_material / r.courses : 0;
                  return (
                    <tr key={r.programme_id}>
                      <td className="px-4 py-2.5">
                        <Link to={paths.programme(r.campus_id, r.programme_id)} className="hover:text-brand">
                          <span className="code mr-3 font-semibold text-brand">{r.short}</span>
                          <span className="text-ink">{r.programme}</span>
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-ink-soft" data-numeric>
                        {r.year ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-ink-soft" data-numeric>
                        {r.courses || "not read yet"}
                      </td>
                      <td className="px-4 py-2.5">
                        {r.courses === 0 ? (
                          <span className="text-xs text-ink-faint">no course list to fill</span>
                        ) : (
                        <div className="flex items-center gap-3">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
                            <div className="h-full rounded-full bg-confirmed" style={{ width: `${share * 100}%` }} />
                          </div>
                          <span className="w-16 text-right text-ink-soft" data-numeric>
                            {r.with_material} / {r.courses}
                          </span>
                        </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
