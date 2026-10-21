/**
 * The first page: Amrita University and its five campuses.
 *
 * A student knows their campus before anything else, so the campuses are the
 * page. Search is beside them for the student who knows the course code.
 */

import { Link } from "react-router-dom";

import { ErrorNote, Icon, PageHeader, SkeletonCards } from "@ai/core";

import { useHealth, useTree } from "../api";
import { ROOT, paths, plural } from "../ui/bits";
import { SearchBox } from "./SearchPage";

export function LibraryHome() {
  const tree = useTree();
  const health = useHealth();
  const university = tree.data?.institution?.display ?? "Amrita University";

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={university}
        title="Course library"
        subtitle="Every B.Tech and AI course by campus, branch and semester, with material to prepare its viva."
        how={
          <>
            <p>
              The courses are read from each programme's latest curriculum on amrita.edu: its
              semester tables, its electives, and the syllabus page for each course. A course
              taught at two campuses is one course, so material added at Coimbatore is there for
              Amritapuri too.
            </p>
            <p className="mt-2">
              A branch appears under a campus only if the programme's own page lists that campus.
            </p>
          </>
        }
      >
        {health.data && (
          <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm" data-numeric>
            <div>
              <dt className="text-ink-faint">Branches</dt>
              <dd className="text-lg font-semibold text-ink">{health.data.programmes}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">Courses</dt>
              <dd className="text-lg font-semibold text-ink">{health.data.courses}</dd>
            </div>
            <div>
              <dt className="text-ink-faint">Materials</dt>
              <dd className="text-lg font-semibold text-ink">{health.data.materials}</dd>
            </div>
          </dl>
        )}
      </PageHeader>

      <SearchBox />

      <section aria-labelledby="campuses">
        <h2 id="campuses" className="eyebrow mb-3">
          Campuses
        </h2>
        {tree.isPending && <SkeletonCards label="Loading the campuses" cards={5} />}
        {tree.isError && (
          <ErrorNote message="The campuses did not load." onRetry={() => tree.refetch()} />
        )}
        {tree.data && (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tree.data.campuses.map((campus) => (
              <li key={campus.id}>
                <Link
                  to={paths.campus(campus.id)}
                  className="group flex items-center justify-between rounded-xl border border-line bg-surface px-5 py-4 transition-colors hover:border-brand-line"
                >
                  <span>
                    <span className="block font-semibold text-ink group-hover:text-brand">
                      {campus.name}
                    </span>
                    <span className="text-sm text-ink-soft">
                      {plural(campus.programmes, "branch", "branches")}
                    </span>
                  </span>
                  <Icon name="building" size={20} className="text-ink-faint" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-sm text-ink-soft">
        Which courses still have nothing to prepare from?{" "}
        <Link to={`${ROOT}/coverage`} className="font-medium text-brand hover:underline">
          See coverage
        </Link>
      </p>
    </div>
  );
}
