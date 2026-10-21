/**
 * A campus: the branches it runs, by school. Only the ones it runs — the
 * programme's page is what says so (EC-20.1).
 */

import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, ErrorNote, PageHeader, SkeletonRows } from "@ai/core";

import { useCampus, useTree } from "../api";
import type { CampusProgramme } from "../types";
import { Pill, ROOT, Trail, paths, plural, rememberCampus } from "../ui/bits";

export function CampusPage() {
  const { campusId = "" } = useParams();
  const campus = useCampus(campusId);
  const tree = useTree();
  const university = tree.data?.institution?.display ?? "Amrita University";
  const found = campus.data?.campus.id;

  useEffect(() => {
    if (found) rememberCampus(found);
  }, [found]);

  if (campus.isError) {
    return (
      <>
        <Trail items={[{ label: university, to: ROOT }, { label: campusId }]} />
        <EmptyState title="No such campus" icon="building">
          The library covers Amritapuri, Coimbatore, Bengaluru, Chennai and Amaravati.
        </EmptyState>
      </>
    );
  }

  const bySchool = new Map<string, CampusProgramme[]>();
  for (const p of campus.data?.programmes ?? []) {
    bySchool.set(p.school, [...(bySchool.get(p.school) ?? []), p]);
  }

  return (
    <div className="space-y-8">
      <div>
        <Trail
          items={[{ label: university, to: ROOT }, { label: campus.data?.campus.name ?? "…" }]}
        />
        <PageHeader
          title={campus.data?.campus.name ?? "Campus"}
          subtitle={
            campus.data
              ? `${plural(campus.data.programmes.length, "branch", "branches")} run here. Pick yours to see its semesters.`
              : undefined
          }
        />
      </div>

      {campus.isPending && <SkeletonRows label="Loading the branches" rows={6} />}
      {campus.data && campus.data.programmes.length === 0 && (
        <ErrorNote message="No branch is listed at this campus yet." />
      )}

      {[...bySchool.entries()].map(([school, programmes]) => (
        <section key={school} aria-labelledby={`school-${school}`}>
          <h2 id={`school-${school}`} className="eyebrow mb-3">
            {school}
          </h2>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {programmes.map((p) => (
              <li key={p.id}>
                <Link
                  to={paths.programme(campusId, p.id)}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5 transition-colors hover:bg-surface-sunken"
                >
                  <span className="code w-24 shrink-0 font-semibold text-brand">{p.short}</span>
                  <span className="min-w-0 flex-1 font-medium text-ink">
                    {p.degree} {p.name}
                  </span>
                  {p.curriculum_status === "parsed" ? (
                    <span className="text-sm text-ink-soft" data-numeric>
                      {p.curriculum_year} curriculum · {plural(p.courses, "course")}
                      {p.materials > 0 && ` · ${plural(p.materials, "material")}`}
                    </span>
                  ) : (
                    <Pill tone="reported" title="Its curriculum PDF is listed but was not read.">
                      courses not read yet
                    </Pill>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
