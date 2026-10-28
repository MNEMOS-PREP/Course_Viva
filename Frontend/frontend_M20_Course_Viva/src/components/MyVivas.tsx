/**
 * Your vivas, newest first: one still open to go back to, and every report.
 */

import { Link } from "react-router-dom";

import { EmptyState, ErrorNote, PageHeader, SkeletonRows } from "@ai/core";

import { Pill, ROOT } from "../ui/bits";
import { useMyVivas } from "../vivaApi";

export function MyVivas() {
  const vivas = useMyVivas();
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Your vivas"
        subtitle="Practice vivas on your course material, and what each one showed."
      />
      {vivas.isPending ? (
        <SkeletonRows label="Loading your vivas" rows={4} />
      ) : vivas.isError ? (
        <ErrorNote message="Your vivas did not load." detail={vivas.error.message} onRetry={() => vivas.refetch()} />
      ) : vivas.data.length === 0 ? (
        <EmptyState
          title="No vivas yet"
          icon="mic"
          action={
            <Link to={ROOT} className="inline-flex h-9 items-center rounded-lg bg-brand px-3.5 text-sm font-semibold text-on-brand">
              Find your course
            </Link>
          }
        >
          Open one of your courses, add your notes or lab manual, and start a viva on it.
        </EmptyState>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {vivas.data.map((v) => (
            <li key={v.id}>
              <Link
                to={v.status === "live" ? `/viva/${v.id}` : `/viva/${v.id}/report`}
                className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5 hover:bg-surface-sunken"
              >
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-ink">{v.scope}</span>
                  <span className="text-xs text-ink-faint">
                    {v.course && <span className="code mr-2">{v.course.code}</span>}
                    {v.course?.title} · {new Date(v.started_at).toLocaleDateString()}
                  </span>
                </span>
                {v.status === "live" ? (
                  <Pill tone="brand">in progress</Pill>
                ) : (
                  <span className="text-sm text-ink-soft" data-numeric>
                    {v.correct} of {v.answered} right
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
