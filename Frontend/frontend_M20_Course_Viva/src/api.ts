/**
 * M20 — Course Viva · API client.
 *
 * Spec: plan_in_depth/M20_Course_Viva.md §7 (API)
 *
 * One hook per backend endpoint, and no hook without one. Uploads go through a
 * raw `fetch` with the session's headers, because `api` sets a JSON content
 * type and a multipart body needs the browser to set its own boundary.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, sessionHeaders } from "@ai/core";

import type {
  CampusView,
  CourseView,
  CoverageRow,
  Health,
  ImportDone,
  ImportDryRun,
  Material,
  MaterialPages,
  ProgrammeView,
  SearchResult,
  Tree,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";
const L = "/v1/library";

export const m20Keys = {
  health: ["m20", "health"] as const,
  tree: ["m20", "tree"] as const,
  campus: (id: string) => ["m20", "campus", id] as const,
  programme: (id: string, year?: number) => ["m20", "programme", id, year ?? null] as const,
  course: (id: string) => ["m20", "course", id] as const,
  pages: (id: string) => ["m20", "pages", id] as const,
  search: (q: string) => ["m20", "search", q] as const,
  coverage: ["m20", "coverage"] as const,
};

/** Course ids carry a colon ("btech-cse-2023:23CSE201"): keep it in the path. */
const seg = (id: string) => encodeURIComponent(id).replace(/%3A/gi, ":");

/**
 * Open a material's file in a new tab. Fetched with the session's headers and
 * opened as a blob: a plain link carries no headers, so private and held
 * material — exactly what its owner wants to open — would answer 404.
 */
export async function openFile(materialId: string): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const blob = await api.getBlob(`${L}/materials/${seg(materialId)}/file`);
    const url = URL.createObjectURL(blob);
    if (tab) tab.location.href = url;
    else window.location.href = url;
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) {
    tab?.close();
    throw error;
  }
}

export function useHealth() {
  return useQuery({
    queryKey: m20Keys.health,
    queryFn: () => api.get<Health>("/health"),
    retry: false,
  });
}

export function useTree() {
  return useQuery({ queryKey: m20Keys.tree, queryFn: () => api.get<Tree>(`${L}/tree`) });
}

export function useCampus(id: string) {
  return useQuery({
    queryKey: m20Keys.campus(id),
    queryFn: () => api.get<CampusView>(`${L}/campuses/${seg(id)}`),
  });
}

export function useProgramme(id: string, year?: number) {
  return useQuery({
    queryKey: m20Keys.programme(id, year),
    queryFn: () =>
      api.get<ProgrammeView>(`${L}/programmes/${seg(id)}${year ? `?year=${year}` : ""}`),
  });
}

export function useCourse(id: string) {
  return useQuery({
    queryKey: m20Keys.course(id),
    queryFn: () => api.get<CourseView>(`${L}/courses/${seg(id)}`),
  });
}

export function useMaterialPages(id: string | null) {
  return useQuery({
    queryKey: m20Keys.pages(id ?? ""),
    queryFn: () => api.get<MaterialPages>(`${L}/materials/${seg(id!)}/pages`),
    enabled: id !== null,
  });
}

export function useSearch(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: m20Keys.search(query),
    queryFn: () => api.get<SearchResult>(`${L}/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
    placeholderData: (previous) => previous,
  });
}

export function useCoverage() {
  return useQuery({
    queryKey: m20Keys.coverage,
    queryFn: () => api.get<CoverageRow[]>(`${L}/coverage`),
  });
}

/** A multipart POST with the session's headers and the platform's error shape. */
async function postForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    body,
    headers: sessionHeaders(),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const parsed = await response.json();
      detail = parsed.detail ?? detail;
    } catch {
      /* non-JSON error body — keep the status text */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export interface AddMaterialInput {
  file?: File;
  url?: string;
  title?: string;
  kind: string;
  unit?: string;
  visibility: "private" | "platform";
  permission?: string;
  /** The campus it was added from: a tag, not a wall (FR-20.10). */
  campus_id?: string;
}

export function useAddMaterial(courseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AddMaterialInput) => {
      const form = new FormData();
      if (input.file) form.append("file", input.file);
      if (input.url) form.append("url", input.url);
      for (const key of ["title", "kind", "unit", "visibility", "permission", "campus_id"] as const) {
        const value = input[key];
        if (value) form.append(key, value);
      }
      return postForm<{ created: boolean; material: Material }>(
        `${L}/courses/${seg(courseId)}/materials`,
        form,
      );
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["m20"] }),
  });
}

export function useApprove() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (materialId: string) =>
      api.post<{ material: Material }>(`${L}/materials/${seg(materialId)}/approve`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["m20"] }),
  });
}

export function useTakeDown() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (materialId: string) =>
      api.del<{ removed: string }>(`${L}/materials/${seg(materialId)}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["m20"] }),
  });
}

/** Where the empty folder tree downloads from (FR-20.6). */
export const FOLDERS_ZIP = `${BASE}${L}/folders.zip`;

/** A file's path inside the chosen folder: what the importer reads. */
export const pathOf = (file: File) => file.webkitRelativePath || file.name;

/**
 * Starlette parses at most 1,000 files per form, and one request of a whole
 * semester's PDFs is one long wait with no progress. So both steps go up in
 * batches: the plan by count, the import by count and size.
 */
const PLAN_BATCH = 500;
const RUN_BATCH_FILES = 25;
const RUN_BATCH_BYTES = 40 * 1024 * 1024;

/**
 * The dry run reads only paths, so it sends each path with an empty body —
 * a 2 GB folder is planned in a second, and nothing is uploaded twice.
 */
export async function planImport(files: File[], shared: boolean): Promise<ImportDryRun> {
  const out: ImportDryRun = { dry_run: true, would_add: [], problems: [] };
  for (let i = 0; i < files.length; i += PLAN_BATCH) {
    const form = new FormData();
    for (const file of files.slice(i, i + PLAN_BATCH)) form.append("files", new Blob([]), pathOf(file));
    const part = await postForm<ImportDryRun>(`${L}/import?dry_run=true&shared=${shared}`, form);
    out.would_add.push(...part.would_add);
    out.problems.push(...part.problems);
  }
  return out;
}

function batches(files: File[]): File[][] {
  const out: File[][] = [];
  let current: File[] = [];
  let bytes = 0;
  for (const file of files) {
    if (current.length && (current.length >= RUN_BATCH_FILES || bytes + file.size > RUN_BATCH_BYTES)) {
      out.push(current);
      current = [];
      bytes = 0;
    }
    current.push(file);
    bytes += file.size;
  }
  if (current.length) out.push(current);
  return out;
}

/** Upload the files the plan placed, batch by batch, reporting how far it got. */
export async function runImport(
  files: File[],
  shared: boolean,
  onProgress: (sent: number, total: number) => void,
): Promise<ImportDone> {
  const out: ImportDone = { dry_run: false, added: 0, already_there: 0, problems: [] };
  let sent = 0;
  onProgress(0, files.length);
  for (const batch of batches(files)) {
    const form = new FormData();
    for (const file of batch) form.append("files", file, pathOf(file));
    try {
      const part = await postForm<ImportDone>(`${L}/import?dry_run=false&shared=${shared}`, form);
      out.added += part.added;
      out.already_there += part.already_there;
      out.problems.push(...part.problems);
    } catch (error) {
      // One failed batch is reported against its files; the rest still go up.
      const reason = error instanceof Error ? error.message : "the upload failed";
      out.problems.push(...batch.map((file) => ({ path: pathOf(file), reason })));
    }
    sent += batch.length;
    onProgress(sent, files.length);
  }
  return out;
}

export function useRefreshLibrary() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ["m20"] });
}
