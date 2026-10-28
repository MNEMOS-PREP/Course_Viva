/**
 * M20 — Course Viva · the viva's hooks, one per /v1/vivas endpoint.
 *
 * Every answer returns the whole state, so the room is the server's word on
 * the conversation; nothing is appended locally and later reconciled.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@ai/core";

import type {
  AnswerTiming,
  BankQuestion,
  MaterialBank,
  StartVivaInput,
  VivaProgress,
  VivaReport,
  VivaScope,
  VivaState,
  VivaSummary,
} from "./vivaTypes";

const V = "/v1/vivas";
/** Course ids carry a colon ("btech-cse-2023:23CSE201"): keep it in the path. */
const seg = (id: string) => encodeURIComponent(id).replace(/%3A/gi, ":");

export const vivaKeys = {
  scopes: ["m20", "viva", "scope"] as const,
  scope: (courseId: string) => ["m20", "viva", "scope", courseId] as const,
  state: (id: string) => ["m20", "viva", "state", id] as const,
  report: (id: string) => ["m20", "viva", "report", id] as const,
  mine: ["m20", "viva", "mine"] as const,
  progress: ["m20", "viva", "progress"] as const,
  bank: (materialId: string, retired: boolean) => ["m20", "viva", "bank", materialId, retired] as const,
};

export function useVivaScope(courseId: string) {
  return useQuery({
    queryKey: vivaKeys.scope(courseId),
    queryFn: () => api.get<VivaScope>(`${V}/scope/${seg(courseId)}`),
  });
}

export function useStartViva() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: StartVivaInput) => api.post<VivaState>(V, input),
    onSuccess: (state) => {
      client.setQueryData(vivaKeys.state(state.id), state);
      client.invalidateQueries({ queryKey: vivaKeys.mine });
      // The next viva has the next examiner, and a viva left open was ended.
      client.invalidateQueries({ queryKey: vivaKeys.scopes });
    },
  });
}

export function useViva(id: string) {
  return useQuery({
    queryKey: vivaKeys.state(id),
    queryFn: () => api.get<VivaState>(`${V}/${seg(id)}`),
    refetchOnWindowFocus: false,
  });
}

function useStep<T>(id: string, step: (input: T) => Promise<VivaState>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: step,
    onSuccess: (state) => {
      client.setQueryData(vivaKeys.state(id), state);
      if (state.status === "ended") {
        client.invalidateQueries({ queryKey: vivaKeys.mine });
        client.invalidateQueries({ queryKey: vivaKeys.report(id) });
        // A part done, and the next one banked meanwhile: the start panel's
        // "done" and "ready" have changed.
        client.invalidateQueries({ queryKey: vivaKeys.scopes });
        client.invalidateQueries({ queryKey: vivaKeys.progress });
      }
    },
  });
}

export function useAnswer(id: string) {
  return useStep(id, (input: { text: string; timing?: AnswerTiming }) =>
    api.post<VivaState>(`${V}/${seg(id)}/answer`, input),
  );
}

export function useHint(id: string) {
  return useStep(id, () => api.post<VivaState>(`${V}/${seg(id)}/hint`));
}

export function useEndViva(id: string) {
  return useStep(id, () => api.post<VivaState>(`${V}/${seg(id)}/end`));
}

export function useVivaReport(id: string) {
  return useQuery({
    queryKey: vivaKeys.report(id),
    queryFn: () => api.get<VivaReport>(`${V}/${seg(id)}/report`),
  });
}

export function useMyVivas() {
  return useQuery({ queryKey: vivaKeys.mine, queryFn: () => api.get<VivaSummary[]>(V) });
}

/** A material's questions, for the placement cell to review (FR-20.14). */
export function useBank(materialId: string, retired = false) {
  return useQuery({
    queryKey: vivaKeys.bank(materialId, retired),
    queryFn: () =>
      api.get<MaterialBank>(`${V}/bank/${seg(materialId)}${retired ? "?retired=true" : ""}`),
  });
}

export function useReviewQuestion(materialId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; status: BankQuestion["status"] }) =>
      api.post<BankQuestion>(`${V}/bank/questions/${seg(input.id)}`, { status: input.status }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["m20", "viva", "bank", materialId] }),
  });
}

/** The student's progress over their vivas (progress.py). */
export function useVivaProgress() {
  return useQuery({
    queryKey: vivaKeys.progress,
    queryFn: () => api.get<VivaProgress>(`${V}/progress`),
  });
}
