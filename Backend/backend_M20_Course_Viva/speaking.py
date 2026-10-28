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
        "silence_ms": int(silence) if isinstance(silence, (int, float)) and silence >= 0 else None,
        "wpm": pace,
        "spoken": spoken,
        "unfinished": unfinished(text),
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
