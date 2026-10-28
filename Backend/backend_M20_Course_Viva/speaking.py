"""How an answer sounded (FR-20.17), and whether it is getting better (AC-20.6).

The student who freezes in vivas knows the answer in writing (spec §2.1); what
they need to see is the speaking get easier. So per answer:

  words        how much was said
  fillers      "um", "uh", "basically", "you know", a "like" that fills —
               counted the way M06's delivery notes count them (`delivery.py`),
               so a student sees one number on the platform, not two
  silence      how long before they started (the client measures it: time from
               the question to the first word spoken or typed)
  pace         words per minute, spoken answers only — typing speed is not
               speaking speed, and saying so beats a misleading number
  unfinished   an answer that stops mid-thought ("…and then the", "so")
  hedges       "I think", "maybe", "probably", "I'm not sure" — the answer said
               less surely than it might be (2026-10-29; no module had a list:
               this is it, and M06's delivery notes can take it from here)
  framing      how the answer is put together: does it open with the answer or
               with "um, so, well…"; its sentences and their length; a sentence
               that runs on; reasons given ("because", "so that", "which means")

All of it is counted, not judged by a model.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_WORD = re.compile(r"[a-z']+")
_VOCAL = frozenset({"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm"})
_LEXICAL = ("basically", "actually", "literally", "honestly")
_PHRASES = ("you know", "i mean", "kind of", "sort of")
#: M06's rule (`delivery._LIKE_FILLER`): "like" fills when commas fence it,
#: when it opens a clause, or beside a vocal filler.
_LIKE_FILLER = re.compile(
    r"(?:(?:^|[.!?]\s+|,\s*)like\s*,)|(?:,\s*like\s+(?!this|that|a|an|the)\b)"
    r"|(?:\b(?:um|uh|er)\s*,?\s*like\b)|(?:^\s*like\b)"
    r"|(?:\b(?:and|so|but)\s+like\s*,)|(?:(?<!,\s)(?<!,)\blike\s*,?\s*(?:um|uh|er)\b)",
    re.I,
)
#: Words a finished sentence does not end on.
_DANGLING = frozenset(
    "and or but so because the a an of to with which that then if when is are was were "
    "like um uh".split()
)
#: Saying less surely than one might. Not "kind of" / "sort of": those are
#: M06's fillers, and a word is counted once.
_HEDGES = (
    "i think", "i guess", "i believe", "i feel", "i suppose", "maybe", "perhaps",
    "probably", "possibly", "i'm not sure", "i am not sure", "not sure", "might be",
    "could be", "i don't know if", "if i remember", "if i'm right",
)  # fmt: skip
#: Giving a reason: what an explanation is made of.
_REASONS = (
    "because", "since", "so that", "therefore", "hence", "which means", "that means",
    "as a result", "due to", "that's why", "this is why", "in order to", "so it",
)  # fmt: skip
#: Openings that warm up instead of answering.
_WARM_UP = frozenset({"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "so", "well",
                      "okay", "ok", "like", "basically", "actually", "yeah", "right"})  # fmt: skip
#: A sentence longer than this runs on: the listener has lost its start.
RUN_ON_WORDS = 35
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
#: Below this a spoken answer is too short to have a pace.
MIN_PACE_MS = 2000
#: Vivas the trend is read over.
TREND_OVER = 5


def fillers_in(text: str) -> dict[str, int]:
    lowered = text.lower()
    counts: Counter[str] = Counter()
    for word in _WORD.findall(lowered):
        if word in _VOCAL:
            counts["um/uh"] += 1
        elif word in _LEXICAL:
            counts[word] += 1
    for phrase in _PHRASES:
        counts[phrase] += len(re.findall(rf"\b{phrase}\b", lowered))
    counts["like"] += len(_LIKE_FILLER.findall(text))
    return {k: v for k, v in counts.items() if v}


def hedges_in(text: str) -> int:
    lowered = f" {text.lower()} "
    return sum(len(re.findall(rf"(?<![a-z']){re.escape(h)}(?![a-z'])", lowered)) for h in _HEDGES)


def framing(text: str) -> dict[str, Any]:
    """How an answer is put together, counted from its words."""
    words = _WORD.findall(text.lower())
    sentences = [s for s in _SENTENCE_END.split(text.strip()) if _WORD.search(s.lower())]
    lengths = [len(_WORD.findall(s.lower())) for s in sentences]
    lowered = f" {text.lower()} "
    return {
        # Opens with the answer, not with "um, so, well…".
        "direct": bool(words) and words[0] not in _WARM_UP,
        "sentences": len(sentences),
        "words_per_sentence": round(sum(lengths) / len(lengths), 1) if lengths else None,
        "run_on": sum(1 for n in lengths if n > RUN_ON_WORDS),
        "reasons": sum(
            len(re.findall(rf"(?<![a-z']){re.escape(r)}(?![a-z'])", lowered)) for r in _REASONS
        ),
    }


def unfinished(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith(("...", "…", "-", "—")):
        return True
    words = _WORD.findall(stripped.lower())
    return bool(words) and words[-1] in _DANGLING and not stripped.endswith((".", "?", "!"))


def measure(text: str, timing: dict[str, Any] | None) -> dict[str, Any]:
    """One answer's measures. `timing` is what the client sent, or None."""
    timing = timing or {}
    words = len(_WORD.findall(text.lower()))
    spoken = bool(timing.get("spoken"))
    duration = timing.get("duration_ms")
    silence = timing.get("silence_ms")
    pace = None
    if spoken and isinstance(duration, (int, float)) and duration >= MIN_PACE_MS and words:
        pace = round(words / (duration / 60000))
    fillers = fillers_in(text)
    return {
        "words": words,
        "fillers": fillers,
        "filler_count": sum(fillers.values()),
        "hedges": hedges_in(text),
        "framing": framing(text),
        "silence_ms": int(silence) if isinstance(silence, (int, float)) and silence >= 0 else None,
        "wpm": pace,
        "spoken": spoken,
        "unfinished": unfinished(text),
        # Stopped by the examiner: it went on past what the question needed.
        "cut_in": bool(timing.get("cut_in")),
    }


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def summary(measures: list[dict[str, Any]]) -> dict[str, Any]:
    """One viva's answers, together."""
    words = sum(m["words"] for m in measures)
    filler_total = sum(m["filler_count"] for m in measures)
    by_kind: Counter[str] = Counter()
    for m in measures:
        by_kind.update(m["fillers"])
    silences = [m["silence_ms"] for m in measures if m["silence_ms"] is not None]
    paces = [m["wpm"] for m in measures if m["wpm"] is not None]
    said = [m for m in measures if m["words"]]
    hedges = sum(m.get("hedges", 0) for m in measures)
    framed = [m["framing"] for m in said if m.get("framing")]
    sentence_lengths = [f["words_per_sentence"] for f in framed if f["words_per_sentence"]]
    return {
        "answers": len(measures),
        "words": words,
        "words_per_answer": _mean([m["words"] for m in measures]),
        "fillers": filler_total,
        #: Per hundred words: comparable across long and short vivas.
        "fillers_per_100": round(100 * filler_total / words, 1) if words else None,
        "top_filler": by_kind.most_common(1)[0][0] if by_kind else None,
        "silence_ms_median": sorted(silences)[len(silences) // 2] if silences else None,
        "long_silences": sum(1 for s in silences if s >= 8000),
        "wpm": _mean(paces),
        "spoken_answers": sum(1 for m in measures if m["spoken"]),
        "unfinished": sum(1 for m in measures if m["unfinished"]),
        "hedges": hedges,
        "hedges_per_100": round(100 * hedges / words, 1) if words else None,
        # Of the answers that said something, the share that opened with the answer.
        "direct_share": round(sum(1 for f in framed if f["direct"]) / len(framed), 2)
        if framed
        else None,
        "words_per_sentence": _mean(sentence_lengths),
        "run_on": sum(f["run_on"] for f in framed),
        "cut_in": sum(1 for m in measures if m.get("cut_in")),
    }


def trend(summaries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Oldest first, over the last few vivas: is it getting easier (AC-20.6)?

    A direction only when there are at least three vivas to read it from, and
    only on what was measured in each."""
    recent = summaries[-TREND_OVER:]
    if len(recent) < 3:
        return None

    def direction(key: str, lower_is_better: bool = True) -> str | None:
        values = [s[key] for s in recent if s.get(key) is not None]
        if len(values) < 3:
            return None
        first, last = _mean(values[: len(values) // 2]), _mean(values[len(values) // 2 :])
        if first is None or last is None or first == last:
            return "steady"
        better = last < first if lower_is_better else last > first
        return "better" if better else "worse"

    return {
        "vivas": len(recent),
        "fillers_per_100": [s.get("fillers_per_100") for s in recent],
        "silence_ms_median": [s.get("silence_ms_median") for s in recent],
        "fillers": direction("fillers_per_100"),
        "silences": direction("silence_ms_median"),
    }
