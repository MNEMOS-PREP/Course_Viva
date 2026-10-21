/**
 * Search: courses by code, title or syllabus, and the pages of material that
 * mention the words — with the page number, so the hit can be checked.
 */

import { Fragment, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorNote, Icon, PageHeader, SkeletonRows } from "@ai/core";

import { useSearch } from "../api";
import { KIND_LABEL, ROOT, campusFor, paths, splitCourseId } from "../ui/bits";

export function SearchBox({ initial = "" }: { initial?: string }) {
  const navigate = useNavigate();
  const [q, setQ] = useState(initial);
  useEffect(() => setQ(initial), [initial]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (q.trim().length >= 2) navigate(`${ROOT}/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <form onSubmit={submit} role="search" className="flex max-w-2xl gap-2">
      <label className="relative flex-1">
        <span className="sr-only">Search courses and material</span>
        <Icon name="search" size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-faint" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="A course code, a title, or a topic: 23CSE201, page replacement…"
          className="w-full rounded-lg border border-line bg-surface py-2.5 pr-3 pl-9 text-sm text-ink placeholder:text-ink-faint"
        />
      </label>
      <button type="submit" className="rounded-lg bg-brand px-4 text-sm font-medium text-on-brand hover:bg-brand-hover">
        Search
      </button>
    </form>
  );
}

/** FTS5 wraps the matched words in [ and ]: show them, never inject HTML. */
function Snippet({ text }: { text: string }) {
  const parts = text.split(/(\[[^\]]*\])/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("[") && part.endsWith("]") ? (
          <mark key={i} className="hit text-ink">
            {part.slice(1, -1)}
          </mark>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function courseLink(courseId: string, campuses: string[]): string | null {
  const campus = campusFor(campuses);
  if (!campus) return null;
  const { programme, year, code } = splitCourseId(courseId);
  return paths.course(campus, programme, year, code);
}

export function SearchPage() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const found = useSearch(q);
  const data = found.data;

  return (
    <div className="space-y-6">
      <PageHeader title="Search" subtitle="Courses across every campus and branch, and the pages of material that mention your words." />
      <SearchBox initial={q} />

      {q.trim().length < 2 ? null : found.isPending ? (
        <SkeletonRows label="Searching" rows={5} />
      ) : found.isError ? (
        <ErrorNote message="The search did not run." onRetry={() => found.refetch()} />
      ) : data && !data.courses.length && !data.pages.length ? (
        <EmptyState title={`Nothing matches "${q}"`}>
          Try a course code (23CSE201), part of a title, or one word from the syllabus.
        </EmptyState>
      ) : data ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <section aria-labelledby="hits-courses">
            <h2 id="hits-courses" className="eyebrow mb-3">
              Courses · {data.courses.length}
            </h2>
            <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
              {data.courses.map((c) => {
                const to = courseLink(c.id, c.campuses);
                const body = (
                  <>
                    <span className="code mr-3 text-ink-soft">{c.code}</span>
                    <span className="font-medium text-ink">{c.title}</span>
                    <span className="mt-0.5 block text-xs text-ink-faint" title={c.programme}>
                      <span className="code font-medium text-ink-soft">{c.short}</span> · {c.year}
                      {c.semester ? ` · semester ${c.semester}` : " · elective"}
                      {c.match === "syllabus" && " · its syllabus mentions it"}
                    </span>
                  </>
                );
                return (
                  <li key={c.id}>
                    {to ? (
                      <Link to={to} className="block px-4 py-3 hover:bg-surface-sunken">
                        {body}
                      </Link>
                    ) : (
                      <div className="px-4 py-3">{body}</div>
                    )}
                  </li>
                );
              })}
              {!data.courses.length && <li className="px-4 py-3 text-sm text-ink-faint">No course matches.</li>}
            </ul>
          </section>

          <section aria-labelledby="hits-pages">
            <h2 id="hits-pages" className="eyebrow mb-3">
              In the material · {data.pages.length}
            </h2>
            <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
              {data.pages.map((p) => {
                const to = courseLink(p.course_id, p.campuses);
                return (
                  <li key={`${p.material_id}-${p.page}`} className="px-4 py-3">
                    <p className="text-sm">
                      {to ? (
                        <Link to={to} className="font-medium text-ink hover:text-brand">
                          {p.title}
                        </Link>
                      ) : (
                        <span className="font-medium text-ink">{p.title}</span>
                      )}
                      <span className="code ml-2 text-ink-faint">p. {p.page}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-ink-faint">
                      {KIND_LABEL[p.kind]} · {p.course}
                    </p>
                    <p className="mt-1.5 text-sm text-ink-soft">
                      <Snippet text={p.snippet} />
                    </p>
                  </li>
                );
              })}
              {!data.pages.length && (
                <li className="px-4 py-3 text-sm text-ink-faint">
                  No page of material mentions it yet.
                </li>
              )}
            </ul>
          </section>
        </div>
      ) : null}
    </div>
  );
}
