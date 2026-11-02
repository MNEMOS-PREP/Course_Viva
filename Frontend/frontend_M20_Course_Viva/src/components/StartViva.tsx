/**
 * Start a viva: the step "Viva practice" was missing (2026-11-02).
 *
 * Starting one lives on a course's own page - Library, campus, branch, year,
 * course - which is right for finding a course and wrong for the student who
 * opened "Viva practice" with three vivas on the list and no way to begin a
 * fourth ("there is no way to start a new viva"). So this page is the short
 * way in: the courses they have already vivaed on, one click each, or a search
 * for any other, with the same start form a course page has.
 *
 * `?course=<id>` chooses a course, so a choice survives a reload and a link.
 */

import { Link, useSearchParams } from "react-router-dom";

import { ErrorNote, PageHeader, SkeletonRows } from "@ai/core";

import { useCourse } from "../api";
import { ROOT } from "../ui/bits";
import { useMyVivas } from "../vivaApi";
import { SearchBox } from "./SearchPage";
import { VivaStart } from "./VivaStart";

export const START = "/viva/new";

export function StartViva() {
  const [params] = useSearchParams();
  const courseId = params.get("course");
  return courseId ? <OnCourse courseId={courseId} /> : <ChooseCourse />;
}

function OnCourse({ courseId }: { courseId: string }) {
  const course = useCourse(courseId);
  const c = course.data?.course;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow={c ? <span className="code">{c.code}</span> : undefined}
        title={c ? c.title : "Start a viva"}
        subtitle="Choose what to be examined on."
        actions={
          <Link to={START} className="text-sm font-medium text-brand hover:underline">
            Choose a different course
          </Link>
        }
      />
      {course.isError && (
        <ErrorNote message="That course did not load." detail={course.error.message} onRetry={() => course.refetch()} />
      )}
      <div className="max-w-md">
        <VivaStart courseId={courseId} />
      </div>
    </div>
  );
}

function ChooseCourse() {
  const vivas = useMyVivas();
  // The courses they have been examined on, most recent first, once each.
  const courses = new Map<string, { id: string; code: string; title: string; vivas: number }>();
  for (const v of vivas.data ?? []) {
    if (!v.course) continue;
    const seen = courses.get(v.course.id);
    courses.set(v.course.id, { ...v.course, vivas: (seen?.vivas ?? 0) + 1 });
  }
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        title="Start a viva"
        subtitle="Pick the course to be examined on. You choose which notes, slides or lab manual, and how many questions, next."
      />

      {vivas.isPending ? (
        <SkeletonRows label="Loading your courses" rows={3} />
      ) : (
        courses.size > 0 && (
          <section aria-labelledby="again">
            <h2 id="again" className="eyebrow mb-3">
              Courses you have practised
            </h2>
            <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
              {[...courses.values()].map((c) => (
                <li key={c.id}>
                  <Link
                    to={`${START}?course=${encodeURIComponent(c.id)}`}
                    className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-sunken"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium text-ink">{c.title}</span>
                      <span className="text-xs text-ink-faint">
                        <span className="code mr-2">{c.code}</span>
                        {c.vivas === 1 ? "1 viva so far" : `${c.vivas} vivas so far`}
                      </span>
                    </span>
                    <span className="text-sm font-medium text-brand">Start another</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )
      )}

      <section aria-labelledby="another" className="space-y-3">
        <h2 id="another" className="eyebrow">
          {courses.size > 0 ? "Another course" : "Find your course"}
        </h2>
        <SearchBox />
        <p className="text-sm text-ink-soft">
          Or{" "}
          <Link to={ROOT} className="font-medium text-brand hover:underline">
            browse the course library
          </Link>{" "}
          by campus and branch.
        </p>
      </section>
    </div>
  );
}
