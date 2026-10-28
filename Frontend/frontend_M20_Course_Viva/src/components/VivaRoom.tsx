/**
 * The viva room (FR-20.15): an examiner you can see and hear, answered aloud.
 *
 * ── Seen ───────────────────────────────────────────────────────────────────
 * The examiner is one of the platform's academic interviewers, so M11 has
 * their photograph and, where it has built one, a 3D head whose mouth moves
 * with the voice (`TalkingHead`, as M06's panel uses it). The head looks at
 * the student while they speak and glances away while their answer is read.
 *
 * ── Heard ──────────────────────────────────────────────────────────────────
 * Every examiner line is spoken in the voice M11 casts for that persona
 * (`useInterviewerVoice`), and in the browser's own voice when M11 is not
 * running. The student answers aloud: the room listens once the examiner has
 * finished (`useTurnTaking` — it decides when they have finished, and M11's
 * recogniser writes the whole answer down at once), and sends the words with
 * how long the student waited before starting and how long they spoke — the
 * report's pace and silences (FR-20.17).
 *
 * Typing stays one click away: a student in a library cannot talk, and with
 * M11's recogniser down, typing is the way to answer and the room says so.
 *
 * ── The page is shown after the answer, never before (spec §2.3) ───────────
 * The server leaves the citation out of a question still open.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  EmptyState,
  ErrorNote,
  Icon,
  InterviewerPhoto,
  SkeletonRows,
  TalkingHead,
  VOICE_SUPPORTED,
  serverAsrAvailable,
  useInterviewerFaces,
  useInterviewerVoice,
  useTurnTaking,
  type SpokenTurn,
} from "@ai/core";

import { VerdictBadge } from "../ui/verdict";
import { useAnswer, useEndViva, useHint, useViva } from "../vivaApi";
import { NextPart, scopeLabel } from "./NextPart";
import type { AnswerTiming, Cite, VivaState, VivaTurn } from "../vivaTypes";

const KIND_LABEL: Partial<Record<VivaTurn["kind"], string>> = {
  follow_up: "Follow-up",
  hint: "Hint",
  teach: "The answer",
};

type AnswerBy = "voice" | "typing";
const ANSWER_BY_KEY = "m20.answerBy";

/** The clock a spoken turn's times are on (Core's ledger clock, `nowMs`, not
 *  exported in v0.38.0): epoch milliseconds, from the page's own timer. */
const nowMs = () => Math.round(performance.timeOrigin + performance.now());

function readAnswerBy(fallback: AnswerBy): AnswerBy {
  try {
    const held = localStorage.getItem(ANSWER_BY_KEY);
    return held === "voice" || held === "typing" ? held : fallback;
  } catch {
    return fallback;
  }
}

export function VivaRoom() {
  const { vivaId = "" } = useParams();
  const viva = useViva(vivaId);

  if (viva.isPending) return <SkeletonRows label="Opening the viva" rows={4} />;
  if (viva.isError) {
    return (
      <EmptyState title="No such viva" icon="mic">
        It may have been someone else's, or the link is wrong.{" "}
        <Link to="/viva" className="text-brand hover:underline">
          Your vivas
        </Link>
      </EmptyState>
    );
  }
  return <Room state={viva.data} />;
}

/** The examiner's line the student is answering: the last question,
 *  follow-up or hint. */
function asking(state: VivaState): VivaTurn | undefined {
  return [...state.turns]
    .reverse()
    .find((t) => t.role === "examiner" && ["warmup", "question", "follow_up", "hint"].includes(t.kind));
}

function Room({ state }: { state: VivaState }) {
  const answer = useAnswer(state.id);
  const hint = useHint(state.id);
  const end = useEndViva(state.id);
  const busy = answer.isPending || hint.isPending || end.isPending;
  const error = answer.error ?? hint.error ?? end.error;
  const live = state.status === "live" && state.open !== null;

  // ── The examiner's voice ────────────────────────────────────────────────
  const voice = useInterviewerVoice(state.examiner.voice_id, { personaId: state.examiner.id });
  const faces = useInterviewerFaces();
  /** The last examiner line handed to the voice, until it is heard: M11 takes
   *  a second or two to make it, and in that gap the examiner has not asked
   *  yet — the room said "your turn" and opened the mic (live, 2026-10-28). */
  const [waitingFor, setWaitingFor] = useState<string | null>(null);
  const audible = VOICE_SUPPORTED && voice.enabled && !voice.blocked;
  useEffect(() => {
    if (waitingFor && voice.speakingKey === waitingFor) setWaitingFor(null);
  }, [voice.speakingKey, waitingFor]);
  useEffect(() => {
    if (!waitingFor || voice.speakingKey !== null) return;
    // A voice that never starts must not hold the student back for good —
    // counted only while nothing is being said: a long greeting on a slow
    // machine took 21 s, and a timer from the start gave up during it.
    const timer = window.setTimeout(() => setWaitingFor(null), 20_000);
    return () => window.clearTimeout(timer);
  }, [waitingFor, voice.speakingKey]);
  const speaking = voice.speakingKey !== null || (audible && waitingFor !== null);
  /** The last examiner turn already handed to the voice. */
  const spokenUpTo = useRef<number | null>(null);
  useEffect(() => {
    const examiner = state.turns.filter((t) => t.role === "examiner");
    if (spokenUpTo.current === null) {
      // Opening the room (or coming back to it): say what the examiner said
      // since the student last spoke — the greeting and the warm-up, or the
      // question waiting — and nothing older.
      const lastStudent = Math.max(0, ...state.turns.filter((t) => t.role === "student").map((t) => t.seq));
      spokenUpTo.current = live ? lastStudent : Math.max(0, ...examiner.map((t) => t.seq));
    }
    const fresh = examiner.filter((t) => t.seq > (spokenUpTo.current ?? 0));
    if (!fresh.length) return;
    // A tick later, and the mark moved only then: StrictMode mounts twice
    // in development, and a line queued by the first mount was cancelled by
    // its unmount (M06's opening line, 2026-10-05).
    const timer = window.setTimeout(() => {
      spokenUpTo.current = fresh[fresh.length - 1]!.seq;
      for (const turn of fresh) voice.speak(turn.text, `viva-${state.id}-${turn.seq}`);
      setWaitingFor(`viva-${state.id}-${fresh[fresh.length - 1]!.seq}`);
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.turns.length, state.id]);

  /** When the examiner finished asking: the wait before an answer counts from here. */
  const askedAt = useRef<{ seq: number; at: number } | null>(null);
  const current = asking(state);
  useEffect(() => {
    if (!current) return;
    if (speaking) {
      // Still being asked: the wait starts when they finish (live: a 27.7 s
      // "wait" counted from the line appearing, before it was spoken).
      askedAt.current = null;
      return;
    }
    if (askedAt.current?.seq !== current.seq) askedAt.current = { seq: current.seq, at: nowMs() };
  }, [current, speaking]);

  // ── The student's voice ────────────────────────────────────────────────
  const [answerBy, setAnswerByState] = useState<AnswerBy>(() =>
    readAnswerBy(state.mode === "spoken" ? "voice" : "typing"),
  );
  const setAnswerBy = (by: AnswerBy) => {
    setAnswerByState(by);
    try {
      localStorage.setItem(ANSWER_BY_KEY, by);
    } catch {
      /* this visit only */
    }
  };
  const [recogniser, setRecogniser] = useState<boolean | null>(null);
  useEffect(() => {
    void serverAsrAvailable().then(setRecogniser);
  }, []);
  const [heardNote, setHeardNote] = useState<string | null>(null);

  const send = useCallback(
    (text: string, timing: AnswerTiming) => {
      setHeardNote(null);
      answer.mutate({ text, timing });
    },
    [answer],
  );

  const onTurn = (turn: SpokenTurn) => {
    const said = turn.text?.trim();
    if (!said) {
      setHeardNote("I didn't catch that — say it again, or type it.");
      return;
    }
    const from = askedAt.current?.at;
    send(said, {
      spoken: true,
      duration_ms: Math.max(0, turn.endedAt - turn.startedAt),
      silence_ms: from ? Math.max(0, turn.startedAt - from) : undefined,
    });
  };

  const byVoice = answerBy === "voice" && recogniser === true;
  const listening = useTurnTaking({
    // Open once the examiner has finished: a viva is not a conversation to
    // talk over, and the mic hearing the examiner would be heard as an answer.
    enabled: byVoice && live && !busy && !speaking,
    playing: voice.isSpeaking,
    context: () => current?.text ?? null,
    onTurn,
  });

  const latest = state.turns[state.turns.length - 1];
  const progress = state.open?.kind === "warmup" ? 0 : Math.min(state.open?.item ?? state.asked, state.target);
  const status = speaking
    ? "Speaking"
    : busy
      ? "Thinking"
      : listening.speaking
        ? "Listening"
        : live
          ? "Waiting for your answer"
          : "";

  return (
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-faint">
            {state.course && <span className="code mr-2">{state.course.code}</span>}
            {scopeLabel(state.scope.label, state.part)}
          </p>
          <h1 className="mt-1 text-title font-semibold tracking-tight text-ink">
            {state.style === "lab" ? "Lab viva" : "Viva"} with {state.examiner.name}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-ink-faint" data-numeric>
              {state.open?.kind === "warmup" ? "Warm-up" : `Question ${progress} of ${state.target}`}
            </p>
            <div
              className="mt-1.5 h-1.5 w-36 overflow-hidden rounded-full bg-surface-sunken"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={state.target}
              aria-valuenow={progress}
              aria-label="Questions"
            >
              <div className="h-full bg-brand transition-all" style={{ width: `${(100 * progress) / state.target}%` }} />
            </div>
          </div>
          {state.status === "live" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                if (window.confirm("End the viva here? Your report will have what you answered so far.")) {
                  voice.stop("end");
                  end.mutate(undefined);
                }
              }}
              className="rounded-lg border border-line px-3 py-1.5 text-sm text-ink-soft hover:border-line-strong hover:text-ink"
            >
              End
            </button>
          )}
        </div>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <figure className={`overflow-hidden rounded-2xl border bg-surface ${speaking ? "border-brand ring-2 ring-brand/30" : "border-line"}`}>
            {faces?.has(state.examiner.id) ? (
              <TalkingHead
                persona={state.examiner.id}
                name={state.examiner.name}
                speaking={voice.speakingKey !== null}
                expression={voice.expression}
                listening={listening.speaking}
                thinking={busy && !speaking}
                fallback={<InterviewerPhoto persona={state.examiner.id} name={state.examiner.name} fill backdrop />}
                className="aspect-[4/3] w-full"
              />
            ) : (
              <div className="aspect-[4/3] w-full">
                <InterviewerPhoto persona={state.examiner.id} name={state.examiner.name} fill backdrop />
              </div>
            )}
            <figcaption className="flex items-baseline justify-between gap-3 px-4 py-3">
              <span className="min-w-0">
                <span className="block font-medium text-ink">{state.examiner.name}</span>
                <span className="block truncate text-xs text-ink-faint">{state.examiner.title}</span>
              </span>
              <span className="shrink-0 text-xs font-medium text-brand" aria-live="polite">
                {status}
              </span>
            </figcaption>
          </figure>
          {VOICE_SUPPORTED && (
            <label className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={voice.enabled}
                onChange={(e) => voice.setEnabled(e.target.checked)}
                className="accent-brand"
              />
              Hear the examiner
            </label>
          )}
          {voice.blocked && (
            <p className="mt-2 text-xs text-reported">
              Your browser blocked the sound — click anywhere on the page to hear the examiner.
            </p>
          )}
        </aside>

        <section aria-label="The viva" className="min-w-0">
          <Transcript state={state} busy={answer.isPending} />

          <p aria-live="polite" className="sr-only">
            {latest?.role === "examiner" ? latest.text : ""}
          </p>

          {error && (
            <div className="mt-4">
              <ErrorNote message="That did not go through." detail={error.message} />
            </div>
          )}

          {live && state.open ? (
            <div className="mt-6">
              <AnswerPanel
                key={latest?.seq}
                state={state}
                busy={busy}
                answerBy={answerBy}
                recogniser={recogniser}
                speaking={speaking}
                listening={listening}
                heardNote={heardNote}
                onAnswerBy={setAnswerBy}
                onSend={(text, timing) => send(text, timing)}
                onHint={() => hint.mutate(undefined)}
                onRepeat={() => current && voice.repeat(current.text, `viva-${state.id}-again-${current.seq}`)}
              />
            </div>
          ) : (
            <div className="mt-8 rounded-xl border border-line bg-surface p-5 text-center">
              <p className="font-medium text-ink">The viva is over.</p>
              <Link
                to={`/viva/${state.id}/report`}
                className="mt-3 inline-flex h-9 items-center gap-2 rounded-lg bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-hover"
              >
                See your report <Icon name="arrowRight" size={14} />
              </Link>
              {state.next_part && state.course && (
                <NextPart
                  next={state.next_part}
                  courseId={state.course.id}
                  mode={state.mode}
                  style={state.style}
                  questions={state.target}
                  className="mt-4 border-t border-line pt-4"
                />
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Transcript({ state, busy }: { state: VivaState; busy: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [state.turns.length, busy]);

  return (
    <ol className="space-y-4" aria-label="The viva so far">
      {state.turns.map((turn) =>
        turn.role === "examiner" ? (
          <li key={turn.seq} className="max-w-[90%]">
            {KIND_LABEL[turn.kind] && <p className="eyebrow mb-1">{KIND_LABEL[turn.kind]}</p>}
            <p
              className={`rounded-2xl rounded-tl-sm px-4 py-2.5 text-[0.9375rem] leading-relaxed text-ink ${
                turn.kind === "teach" ? "border border-line bg-surface-sunken" : "bg-surface shadow-card"
              }`}
            >
              {turn.text}
            </p>
            {turn.cite && <CiteNote cite={turn.cite} />}
          </li>
        ) : (
          <li key={turn.seq} className="flex flex-col items-end">
            <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-brand-soft px-4 py-2.5 text-[0.9375rem] leading-relaxed text-ink">
              {turn.text || <span className="text-ink-faint">(no answer)</span>}
            </p>
            {turn.verdict && (
              <span className="mt-1.5">
                <VerdictBadge status={turn.verdict} size="sm" />
              </span>
            )}
          </li>
        ),
      )}
      {busy && (
        <li aria-label="The examiner is considering your answer">
          <p className="inline-block rounded-2xl rounded-tl-sm bg-surface px-4 py-2.5 text-sm text-ink-faint shadow-card">
            {state.examiner.name} is considering your answer…
          </p>
        </li>
      )}
      <div ref={end} />
    </ol>
  );
}

function CiteNote({ cite }: { cite: Cite }) {
  return (
    <details className="mt-1.5 text-xs text-ink-faint">
      <summary className="cursor-pointer hover:text-ink-soft">
        From page {cite.page} of {cite.title}
        {cite.read_from_picture && " · read from the slide's picture"}
      </summary>
      <blockquote className="mt-1.5 border-l-2 border-brand-line pl-3 text-sm leading-relaxed text-ink-soft">
        {cite.quote}
      </blockquote>
    </details>
  );
}

/** How loud the student is, drawn from the listener's level each frame. */
function Meter({ level, on }: { level: () => number; on: boolean }) {
  const bar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!on) return;
    let frame = 0;
    const draw = () => {
      if (bar.current) bar.current.style.transform = `scaleX(${Math.max(0.04, Math.min(1, level()))})`;
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [level, on]);
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
      <div ref={bar} className="h-full origin-left bg-brand transition-transform duration-75" style={{ transform: "scaleX(0.04)" }} />
    </div>
  );
}

function AnswerPanel({
  state,
  busy,
  answerBy,
  recogniser,
  speaking,
  listening,
  heardNote,
  onAnswerBy,
  onSend,
  onHint,
  onRepeat,
}: {
  state: VivaState;
  busy: boolean;
  answerBy: AnswerBy;
  recogniser: boolean | null;
  speaking: boolean;
  listening: ReturnType<typeof useTurnTaking>;
  heardNote: string | null;
  onAnswerBy: (by: AnswerBy) => void;
  onSend: (text: string, timing: AnswerTiming) => void;
  onHint: () => void;
  onRepeat: () => void;
}) {
  const length = state.open?.answer_length;
  const voiceDown = answerBy === "voice" && recogniser === false;
  const typing = answerBy === "typing" || voiceDown;

  const actions = (
    <div className="flex flex-wrap items-center gap-1.5">
      <button type="button" onClick={onRepeat} disabled={busy} className="rounded-lg px-2.5 py-1.5 text-sm text-ink-soft hover:bg-surface-sunken hover:text-ink">
        Repeat the question
      </button>
      {state.open?.hint_available && (
        <button type="button" disabled={busy} onClick={onHint} className="rounded-lg px-2.5 py-1.5 text-sm text-ink-soft hover:bg-surface-sunken hover:text-ink">
          Give me a hint
        </button>
      )}
      {state.open?.kind === "question" && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onSend("I don't know.", { spoken: answerBy === "voice" })}
          className="rounded-lg px-2.5 py-1.5 text-sm text-ink-soft hover:bg-surface-sunken hover:text-ink"
        >
          I don't know
        </button>
      )}
      <button
        type="button"
        onClick={() => onAnswerBy(answerBy === "voice" ? "typing" : "voice")}
        className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-sm text-ink hover:border-line-strong"
      >
        <Icon name={answerBy === "voice" ? "keyboard" : "mic"} size={14} />
        {answerBy === "voice" ? "Type instead" : "Answer aloud"}
      </button>
    </div>
  );

  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
      {length && (
        <p className="mb-2 text-xs text-ink-faint">
          {length === "short" ? "A short answer — a line will do." : "A longer answer — explain it in a few sentences."}
        </p>
      )}
      {typing ? (
        <>
          {voiceDown && (
            <p className="mb-2 text-xs text-reported">
              Spoken answers need the voice engine, which is not running — type your answer for now.
            </p>
          )}
          <TypedAnswer busy={busy} onSend={onSend} long={length === "long"} />
        </>
      ) : (
        <SpokenAnswer
          busy={busy}
          recogniser={recogniser}
          speaking={speaking}
          listening={listening}
          heardNote={heardNote}
          examiner={state.examiner.name}
        />
      )}
      <div className="mt-3 border-t border-line pt-3">{actions}</div>
    </div>
  );
}

function SpokenAnswer({
  busy,
  recogniser,
  speaking,
  listening,
  heardNote,
  examiner,
}: {
  busy: boolean;
  recogniser: boolean | null;
  speaking: boolean;
  listening: ReturnType<typeof useTurnTaking>;
  heardNote: string | null;
  examiner: string;
}) {
  const line = listening.error
    ? listening.error
    : recogniser === null
      ? "Getting the microphone ready…"
      : speaking
        ? `${examiner} is asking — answer when they finish.`
        : busy
          ? "Sending your answer…"
          : listening.writing
            ? "Writing down what you said…"
            : listening.speaking
              ? "Listening — take your time."
              : listening.deciding
                ? "Still listening…"
                : "Your turn: answer aloud.";
  return (
    <div className="space-y-3" aria-live="polite">
      <p className="flex items-center gap-2 text-sm font-medium text-ink">
        <Icon name="mic" size={15} className={listening.active && !speaking ? "text-brand" : "text-ink-faint"} />
        {line}
      </p>
      <Meter level={listening.level} on={listening.active && !speaking} />
      {heardNote && <p className="text-sm text-reported">{heardNote}</p>}
    </div>
  );
}

function TypedAnswer({
  busy,
  long,
  onSend,
}: {
  busy: boolean;
  long: boolean;
  onSend: (text: string, timing: AnswerTiming) => void;
}) {
  const [text, setText] = useState("");
  // Mounted afresh for every examiner line (`key`): this is when it appeared.
  const shownAt = useRef(performance.now());
  const firstKeyAt = useRef<number | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    box.current?.focus();
  }, []);
  const send = () => {
    const said = text.trim();
    if (!said || busy) return;
    const started = firstKeyAt.current ?? performance.now();
    onSend(said, { silence_ms: Math.round(started - shownAt.current), spoken: false });
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      <label htmlFor="viva-answer" className="sr-only">
        Your answer
      </label>
      <textarea
        id="viva-answer"
        ref={box}
        value={text}
        rows={long ? 4 : 2}
        disabled={busy}
        placeholder="Answer the way you would say it to the examiner…"
        onChange={(e) => {
          if (firstKeyAt.current === null) firstKeyAt.current = performance.now();
          setText(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        className="w-full resize-y rounded-lg border border-line bg-canvas px-3 py-2 text-[0.9375rem] leading-relaxed text-ink outline-none placeholder:text-ink-faint focus:border-brand-line"
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-xs text-ink-faint">Enter to send · Shift+Enter for a new line</span>
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-brand px-3.5 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-50"
        >
          Answer <Icon name="send" size={13} />
        </button>
      </div>
    </form>
  );
}
