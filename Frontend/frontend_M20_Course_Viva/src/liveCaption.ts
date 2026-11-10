/**
 * What the student is saying, shown while they say it (2026-11-10).
 *
 * The viva sends a spoken answer when the student has finished — M11 writes
 * it down then (`useTurnTaking`). Until it did, the answer panel said
 * "Listening — take your time" over a level meter and nothing else: a student
 * talking for twenty seconds saw no sign that a word was heard, and read the
 * mic as broken ("the speech-to-text button is there but text doesn't
 * appear"). M06's room has shown a caption since 2026-10-04.
 *
 * The caption is the browser's own recognition (Chrome, Edge, Safari): free,
 * and live word by word. It is only a caption — what is sent and judged is
 * still M11's transcript of the whole turn. Where the browser has none, or it
 * fails (blocked, offline), `working` turns false and the room asks M11 for
 * its rolling caption instead (`useTurnTaking({ caption })`).
 */
import { useEffect, useRef, useState } from "react";

interface RecognitionResult {
  readonly isFinal: boolean;
  readonly 0: { readonly transcript: string };
}

interface RecognitionEvent {
  readonly resultIndex: number;
  readonly results: ArrayLike<RecognitionResult>;
}

interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
}

type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Indian English, as M06's room uses: most laptops here report en-US. */
const LANG = "en-IN";

/** Errors after which this browser's recognition is not tried again. */
const FATAL = new Set(["not-allowed", "service-not-allowed", "network", "audio-capture", "language-not-supported"]);

/**
 * The caption of the turn being spoken. `on` while the mic is open for an
 * answer; `turn` changes for each new question, which starts a fresh caption.
 */
export function useLiveCaption(on: boolean, turn: unknown) {
  const [working, setWorking] = useState(() => recognitionCtor() !== null);
  const [said, setSaid] = useState("");
  const [heard, setHeard] = useState("");
  const recognition = useRef<Recognition | null>(null);
  const wanted = useRef(on);
  wanted.current = on && working;

  useEffect(() => {
    setSaid("");
    setHeard("");
  }, [turn]);

  useEffect(() => {
    const Ctor = recognitionCtor();
    if (!on || !working || !Ctor) return;
    let stopped = false;
    const begin = () => {
      const r = new Ctor();
      r.lang = LANG;
      r.continuous = true;
      r.interimResults = true;
      r.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i]!;
          if (result.isFinal) final += `${result[0].transcript.trim()} `;
          else interim += result[0].transcript;
        }
        if (final) setSaid((before) => `${before}${final}`);
        setHeard(interim);
      };
      r.onerror = (event) => {
        if (FATAL.has(event.error)) {
          stopped = true;
          setWorking(false);
        }
      };
      r.onend = () => {
        setHeard("");
        // Browsers end a "continuous" session after a pause; while the mic
        // is still open for this answer, carry on.
        if (!stopped && wanted.current) {
          try {
            begin();
          } catch {
            setWorking(false);
          }
        }
      };
      recognition.current = r;
      try {
        r.start();
      } catch {
        setWorking(false);
      }
    };
    begin();
    return () => {
      stopped = true;
      recognition.current?.abort();
      recognition.current = null;
      setHeard("");
    };
  }, [on, working]);

  const text = `${said}${heard}`.trim();
  return { working, text };
}
