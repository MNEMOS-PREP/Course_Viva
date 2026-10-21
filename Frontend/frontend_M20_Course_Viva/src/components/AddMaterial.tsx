/**
 * Add a file or a link to a course (FR-20.5, FR-20.11).
 *
 * "Where it is from" is asked, not assumed: faculty notes and lab manuals are
 * someone's work (Trap 6). Shared with everyone and no answer, the upload waits
 * for the placement cell, and the form says so before the student submits.
 */

import { useRef, useState } from "react";
import type { FormEvent } from "react";

import { Button, isStaff, useSession } from "@ai/core";

import { useAddMaterial } from "../api";
import type { MaterialKind } from "../types";
import { KIND_LABEL, KIND_ORDER } from "../ui/bits";

const SOURCES = [
  { value: "my own notes", label: "My own notes or work" },
  { value: "shared by faculty with the class", label: "Shared by faculty with our class" },
  { value: "publicly available", label: "Publicly available (a book site, NPTEL, a university page)" },
  { value: "", label: "Not sure" },
];

/** A material kind, said in the singular. */
const KIND_ONE: Record<MaterialKind, string> = {
  ...KIND_LABEL,
  notes: "Notes",
  lab_manual: "Lab manual",
  question_paper: "Question paper",
  reference: "Reference",
  video: "Video",
};

export function AddMaterial({ courseId, campusId }: { courseId: string; campusId: string }) {
  const session = useSession();
  const staff = isStaff(session);
  const add = useAddMaterial(courseId);
  const fileInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"file" | "link">("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<MaterialKind>("notes");
  const [unit, setUnit] = useState("");
  const [visibility, setVisibility] = useState<"platform" | "private">("platform");
  const [source, setSource] = useState(SOURCES[0].value);
  const [done, setDone] = useState<string | null>(null);

  if (!session) {
    return (
      <div className="rounded-xl border border-line bg-surface px-5 py-4 text-sm text-ink-soft">
        Sign in to add notes, slides or question papers to this course.
      </div>
    );
  }

  const waits = mode === "file" && visibility === "platform" && !source && !staff;
  const ready = mode === "file" ? file !== null : /^https?:\/\//.test(url.trim());

  function submit(event: FormEvent) {
    event.preventDefault();
    setDone(null);
    add.mutate(
      {
        file: mode === "file" ? (file ?? undefined) : undefined,
        url: mode === "link" ? url.trim() : undefined,
        title: title.trim() || undefined,
        kind: mode === "link" && kind === "notes" ? "reference" : kind,
        unit: unit.trim() || undefined,
        visibility,
        permission: mode === "file" ? source || undefined : undefined,
        campus_id: campusId,
      },
      {
        onSuccess: (result) => {
          const m = result.material;
          setDone(
            !result.created
              ? "That is already here, so nothing new was added."
              : m.visibility === "held"
                ? "Added. Only you see it until the placement cell checks where it is from."
                : m.visibility === "private"
                  ? "Added, for you only."
                  : m.text_status === "no_text"
                    ? "Added. It is a scan, so its text is not searchable yet."
                    : "Added for everyone taking this course.",
          );
          setFile(null);
          setUrl("");
          setTitle("");
          setUnit("");
          if (fileInput.current) fileInput.current.value = "";
        },
      },
    );
  }

  const field = "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink";

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-surface px-5 py-4">
      <h2 className="font-semibold text-ink">Add material</h2>

      <div role="group" aria-label="What to add" className="flex rounded-md border border-line p-0.5 text-sm">
        {(["file", "link"] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
            className={`flex-1 rounded px-2 py-1 font-medium ${
              mode === m ? "bg-brand-soft text-brand" : "text-ink-faint hover:text-ink-soft"
            }`}
          >
            {m === "file" ? "A file" : "A link"}
          </button>
        ))}
      </div>

      {mode === "file" ? (
        <label className="block text-sm">
          <span className="mb-1 block text-ink-soft">PDF, Word, PowerPoint or text, up to 50 MB</span>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx,.pptx,.txt,.md,image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-ink-soft file:mr-3 file:rounded-md file:border-0 file:bg-surface-sunken file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink"
          />
        </label>
      ) : (
        <label className="block text-sm">
          <span className="mb-1 block text-ink-soft">Link</span>
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://nptel.ac.in/courses/…" className={field} />
        </label>
      )}

      <label className="block text-sm">
        <span className="mb-1 block text-ink-soft">Title (optional)</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={mode === "file" ? "the file's name" : "the link"} className={field} />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block text-ink-soft">Kind</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as MaterialKind)} className={field}>
            {KIND_ORDER.map((k) => (
              <option key={k} value={k}>
                {KIND_ONE[k]}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-ink-soft">Unit or lab</span>
          <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Unit 3" className={field} />
        </label>
      </div>

      <fieldset className="space-y-1.5 text-sm">
        <legend className="mb-1 text-ink-soft">Who sees it</legend>
        <label className="flex items-center gap-2">
          <input type="radio" checked={visibility === "platform"} onChange={() => setVisibility("platform")} />
          Everyone taking this course on the platform
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" checked={visibility === "private"} onChange={() => setVisibility("private")} />
          Only me
        </label>
      </fieldset>

      {mode === "file" && visibility === "platform" && !staff && (
        <label className="block text-sm">
          <span className="mb-1 block text-ink-soft">Where it is from</span>
          <select value={source} onChange={(e) => setSource(e.target.value)} className={field}>
            {SOURCES.map((s) => (
              <option key={s.label} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {waits && (
            <span className="mt-1.5 block text-xs text-reported">
              Only you will see it until the placement cell checks it.
            </span>
          )}
        </label>
      )}

      <Button type="submit" disabled={!ready || add.isPending}>
        {add.isPending ? "Adding…" : "Add"}
      </Button>
      {add.error && <p className="text-sm text-contested">{add.error.message}</p>}
      {done && <p className="text-sm text-confirmed">{done}</p>}
      <p className="text-xs text-ink-faint">
        Nothing here is public on the internet, and whoever added a file can take it down.
      </p>
    </form>
  );
}
