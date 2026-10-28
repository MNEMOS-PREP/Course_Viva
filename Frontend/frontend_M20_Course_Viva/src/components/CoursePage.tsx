/**
 * A course: what it covers, and everything there is to prepare its viva from.
 *
 * The material is the page; the syllabus sits beside it, because a student
 * opening a course a week before the viva wants the notes first and the unit
 * list to check them against second.
 */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, ErrorNote, Icon, PageHeader, SkeletonRows, isStaff, useSession } from "@ai/core";

import { openFile, useApprove, useCampus, useCourse, useMaterialPages, useTakeDown, useTree } from "../api";
import type { CourseView, Material } from "../types";
import { KIND_LABEL, KIND_ORDER, Pill, ROOT, Trail, paths, plural, sizeOf } from "../ui/bits";
import { AddMaterial } from "./AddMaterial";
import { VivaStart } from "./VivaStart";

export function CoursePage() {
  const { campusId = "", programmeId = "", year = "", code = "" } = useParams();
  const courseId = `${programmeId}-${year}:${code}`;
  const course = useCourse(courseId);
  const campus = useCampus(campusId);
  const tree = useTree();
  const view = course.data;
  const university = tree.data?.institution?.display ?? "Amrita University";
  const sem = view?.course.semester;

  const trail = (
    <Trail
      items={[
        { label: university, to: ROOT },
        { label: campus.data?.campus.name ?? campusId, to: paths.campus(campusId) },
        {
          label: view?.programme?.short ?? "Branch",
          to: paths.programme(campusId, programmeId, { year: Number(year) || undefined }),
        },
        ...(view
          ? [
              {
                label: sem ? `Semester ${sem}` : (view.course.basket ?? "Electives"),
                to: paths.programme(campusId, programmeId, {
                  year: Number(year) || undefined,
                  sem: sem ? String(sem) : "electives",
                }),
              },
            ]
          : []),
        { label: code },
      ]}
    />
  );

  if (course.isError) {
    return (
      <>
        {trail}
        <EmptyState title="No such course" icon="layers">
          It is not in the {year} curriculum.{" "}
          <Link to={paths.programme(campusId, programmeId)} className="text-brand hover:underline">
            Back to the branch
          </Link>
        </EmptyState>
      </>
    );
  }
  if (!view) {
    return (
      <>
        {trail}
        <SkeletonRows label="Loading the course" rows={6} />
      </>
    );
  }

  const c = view.course;
  const facts = [
    c.ltp && `L-T-P ${c.ltp}`,
    c.credits && `${c.credits} credits`,
    c.category,
    view.curriculum && `${view.curriculum.year} curriculum`,
  ].filter(Boolean);

  return (
    <div className="space-y-8">
      <div>
        {trail}
        <PageHeader
          eyebrow={<span className="code">{c.code}</span>}
          title={c.title}
          subtitle={facts.join(" · ")}
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-8">
          <Materials view={view} />
          <Syllabus view={view} />
        </div>
        <aside className="space-y-4">
          <VivaStart courseId={courseId} />
          <AddMaterial courseId={courseId} campusId={campusId} />
        </aside>
      </div>
    </div>
  );
}

function Materials({ view }: { view: CourseView }) {
  if (!view.materials.length) {
    return (
      <EmptyState title="Nothing here yet" icon="document">
        No notes, slides, lab manuals or question papers for this course yet. Add the first one;
        everyone taking it at any campus will see it.
      </EmptyState>
    );
  }
  const groups = KIND_ORDER.map((kind) => ({
    kind,
    items: view.materials.filter((m) => m.kind === kind),
  })).filter((g) => g.items.length);

  return (
    <section aria-labelledby="materials" className="space-y-5">
      <h2 id="materials" className="font-semibold text-ink">
        Material <span className="text-sm font-normal text-ink-faint">{view.materials.length}</span>
      </h2>
      {groups.map((group) => (
        <div key={group.kind}>
          <h3 className="eyebrow mb-2">{KIND_LABEL[group.kind]}</h3>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {group.items.map((m) => (
              <MaterialRow key={m.id} material={m} />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function MaterialRow({ material: m }: { material: Material }) {
  const session = useSession();
  const staff = isStaff(session);
  const mine = session?.subject === m.added_by;
  const takeDown = useTakeDown();
  const approve = useApprove();
  const [reading, setReading] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  return (
    <li className="px-5 py-3.5">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">
            {m.unit && <span className="mr-2 text-ink-soft">{m.unit}</span>}
            {m.title}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-faint">
            {m.url ? (
              <span>link</span>
            ) : (
              <span data-numeric>
                {m.pages > 0 && `${plural(m.pages, "page")} · `}
                {sizeOf(m.bytes)}
              </span>
            )}
            {m.text_status === "no_text" && (
              <span title="A scan or an image: no text to search or ask questions from yet.">
                scanned · not searchable
              </span>
            )}
            {m.text_status === "failed" && <span>could not be read</span>}
            {m.visibility === "private" && <Pill>only you</Pill>}
            {m.visibility === "held" && (
              <Pill tone="reported" title="Shared without saying where it is from: the placement cell checks it first.">
                waiting for the placement cell
              </Pill>
            )}
            <time dateTime={m.created_at}>{new Date(m.created_at).toLocaleDateString()}</time>
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 text-sm">
          {m.url ? (
            <a href={m.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-brand hover:underline">
              Open <Icon name="link" size={13} />
            </a>
          ) : (
            <button
              type="button"
              onClick={() => {
                setOpenError(null);
                openFile(m.id).catch((e: Error) => setOpenError(e.message));
              }}
              className="font-medium text-brand hover:underline"
            >
              Open
            </button>
          )}
          {m.text_status === "ok" && (
            <button type="button" onClick={() => setReading(!reading)} className="text-ink-soft hover:text-ink" aria-expanded={reading}>
              {reading ? "Hide text" : "Read text"}
            </button>
          )}
          {staff && m.visibility === "held" && (
            <button type="button" onClick={() => approve.mutate(m.id)} disabled={approve.isPending} className="font-medium text-confirmed hover:underline">
              Share with everyone
            </button>
          )}
          {(staff || mine) && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm(`Take down "${m.title}"? It leaves every view and search.`)) {
                  takeDown.mutate(m.id);
                }
              }}
              disabled={takeDown.isPending}
              className="text-ink-faint hover:text-contested"
            >
              Take down
            </button>
          )}
        </div>
      </div>
      {openError && <p className="mt-2 text-xs text-contested">{openError}</p>}
      {(takeDown.error || approve.error) && (
        <p className="mt-2 text-xs text-contested">{(takeDown.error ?? approve.error)?.message}</p>
      )}
      {reading && <PagesText materialId={m.id} />}
    </li>
  );
}

function PagesText({ materialId }: { materialId: string }) {
  const pages = useMaterialPages(materialId);
  if (pages.isPending) return <SkeletonRows label="Loading the text" rows={3} className="mt-3" />;
  if (pages.isError) return <ErrorNote message="The text did not load." />;
  return (
    <div className="mt-3 max-h-96 space-y-4 overflow-y-auto rounded-lg border border-line bg-surface-sunken p-4 text-sm">
      {pages.data.pages.map((p) => (
        <div key={p.page}>
          <p className="code mb-1 text-ink-faint">page {p.page}</p>
          <p className="syllabus text-ink">{p.text}</p>
        </div>
      ))}
    </div>
  );
}

/** A line that starts a section of a syllabus page. */
const HEADING =
  /^(unit|module|lab|experiment|part|text\s*books?|reference(?:\s*books?)?s?|course\s+(?:objectives?|outcomes?)|objectives?|outcomes?|co\s?\d+|evaluation\s+pattern|skills?\s+acquired)\b/i;

/**
 * The curriculum PDF wraps lines at its column width, so a sentence arrives
 * cut in three. Lines are joined back into paragraphs, and a new block starts
 * at each heading ("Unit 2", "Text Books") — which is set as a heading.
 */
function reflow(text: string): { heading: string | null; body: string }[] {
  const blocks: { heading: string | null; body: string }[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const head = HEADING.exec(line);
    if (head) {
      // "Unit 1 Overview of ..." keeps its first words as the heading.
      const short = line.length <= 40;
      blocks.push({ heading: short ? line : null, body: short ? "" : line });
      continue;
    }
    const last = blocks[blocks.length - 1];
    if (!last) blocks.push({ heading: null, body: line });
    else last.body = last.body ? `${last.body}${last.body.endsWith("-") ? "" : " "}${line}` : line;
  }
  return blocks;
}

function SyllabusText({ text }: { text: string }) {
  return (
    <div className="max-w-[72ch] space-y-3 text-sm leading-relaxed text-ink">
      {reflow(text).map((block, i) => (
        <div key={i}>
          {block.heading && <h3 className="font-semibold text-ink">{block.heading}</h3>}
          {block.body && <p className={block.heading ? "mt-0.5" : ""}>{block.body}</p>}
        </div>
      ))}
    </div>
  );
}

function Syllabus({ view }: { view: CourseView }) {
  const c = view.course;
  const pdf = view.curriculum?.parsed_from;
  return (
    <section aria-labelledby="syllabus" className="rounded-xl border border-line bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
        <h2 id="syllabus" className="font-semibold text-ink">
          Syllabus
        </h2>
        {pdf && (
          <a
            href={c.syllabus_page ? `${pdf}#page=${c.syllabus_page}` : pdf}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm text-brand hover:underline"
          >
            <Icon name="document" size={14} />
            {c.syllabus_page ? `Page ${c.syllabus_page} of the curriculum PDF` : "The curriculum PDF"}
          </a>
        )}
      </header>
      <div className="px-5 py-4">
        {c.syllabus ? (
          <SyllabusText text={c.syllabus} />
        ) : (
          <p className="text-sm text-ink-soft">
            The curriculum PDF had no syllabus page the library could match to this course.
          </p>
        )}
      </div>
    </section>
  );
}
