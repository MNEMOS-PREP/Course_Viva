"""A student's progress over their vivas (the user, 2026-10-29: "only when
students see their progress bar and strengths and weaknesses can they
improve").

Everything here is already measured, viva by viva — the verdict on each
answer, how long the student waited, what they said and how — and shown
together: where they are now, where they started, whether it is moving, and
what to do about the weakest. Nothing is scored by a model and nothing is a
grade: a measure, its band, and what it means.

── The bands ─────────────────────────────────────────────────────────────────

Where a measure is good, fair, or worth work. Speaking coaches aim for few
fillers (Yoodli's example takes a speaker from 13 to ~4 per 100 words) and a
conversational 110-160 words a minute; the rest are set from what an
examiner listens for. They say "worth work", never "bad": a band is a hint
about where effort pays, not a judgement.

── Visual skills ─────────────────────────────────────────────────────────────

Eye contact, posture, gestures: not measured yet (the camera is the
multimodal suite's, M12). The response says so rather than leaving a space
that looks like a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from . import speaking
from .marking import _content
from .models import Course, MaterialPage, Question, Viva
from .viva import _item_status, _turns, span_of

#: Vivas the "now" and the "at first" of a measure are read over.
WINDOW = 3
#: A change smaller than this share of where it was is "steady".
STEADY = 0.05


@dataclass(frozen=True)
class Measure:
    key: str
    label: str
    group: str  # answering | speaking | framing
    unit: str  # share | per100 | ms | wpm | words
    #: "higher" or "lower" is better; "band": inside [good_low, good_high].
    better: str
    good: float
    fair: float
    good_high: float | None = None
    fair_high: float | None = None
    #: What it is, in a line.
    means: str = ""
    #: What to do when it is worth work.
    tip: str = ""


MEASURES = (
    Measure(
        "right_first_time",
        "Right first time",
        "answering",
        "share",
        "higher",
        0.7,
        0.5,
        means="Questions answered fully at the first try, with no hint or follow-up.",
        tip="Read again the pages each report lists, then try the questions you missed again.",
    ),
    Measure(
        "explains",
        "Long answers that give a reason",
        "answering",
        "share",
        "higher",
        0.6,
        0.3,
        means="Of the questions asking you to explain, how many answers said why.",
        tip='When a question asks why or how, say the reason: "…because…", "…which means…".',
    ),
    Measure(
        "course_words",
        "In the course's own words",
        "answering",
        "share",
        "higher",
        0.5,
        0.3,
        means="How much of what you say is the material's own terms.",
        tip="Use the words the material uses: an examiner listens for the terms.",
    ),
    Measure(
        "direct",
        "Starts with the answer",
        "framing",
        "share",
        "higher",
        0.7,
        0.5,
        means='Answers that open with the answer, not "um, so, well…".',
        tip="Say the answer first, in one sentence, then explain it.",
    ),
    Measure(
        "words_per_sentence",
        "Words per sentence",
        "framing",
        "words",
        "band",
        8,
        5,
        22,
        30,
        means="Short sentences are easy to follow; very long ones lose the listener.",
        tip="Stop the sentence when the point is made, then start the next one.",
    ),
    Measure(
        "fillers_per_100",
        "Fillers per 100 words",
        "speaking",
        "per100",
        "lower",
        3,
        6,
        means='"Um", "uh", "basically", "you know", a "like" that fills.',
        tip='Pause instead of filling: a silent second sounds surer than "um".',
    ),
    Measure(
        "hedges_per_100",
        "Hesitations per 100 words",
        "speaking",
        "per100",
        "lower",
        1.5,
        3,
        means='"I think", "maybe", "probably", "I\'m not sure".',
        tip='When you know it, say it plainly: drop the "I think".',
    ),
    Measure(
        "wait_ms",
        "Wait before answering",
        "speaking",
        "ms",
        "lower",
        3000,
        6000,
        means="From the end of the question to your first word (your usual wait).",
        tip="Start with the first thing you know; the rest comes while you speak.",
    ),
    Measure(
        "wpm",
        "Pace",
        "speaking",
        "wpm",
        "band",
        110,
        90,
        160,
        180,
        means="Words a minute, on answers spoken aloud.",
        tip="Aim for a steady conversational pace: not rushed, not halting.",
    ),
    Measure(
        "unfinished",
        "Answers left unfinished",
        "speaking",
        "share",
        "lower",
        0.05,
        0.15,
        means='Answers that stop mid-thought ("…and then the").',
        tip="Finish the sentence before you stop, even if the answer is short.",
    ),
)


def band(measure: Measure, value: float | None) -> str | None:
    if value is None:
        return None
    if measure.better == "higher":
        return "good" if value >= measure.good else "fair" if value >= measure.fair else "work"
    if measure.better == "lower":
        return "good" if value <= measure.good else "fair" if value <= measure.fair else "work"
    low, high = measure.good, measure.good_high or measure.good
    if low <= value <= high:
        return "good"
    if measure.fair <= value <= (measure.fair_high or high):
        return "fair"
    return "work"


def _mean(values: list[float | None]) -> float | None:
    have = [v for v in values if v is not None]
    return round(sum(have) / len(have), 3) if have else None


def _direction(measure: Measure, first: float | None, now: float | None) -> str | None:
    if first is None or now is None:
        return None
    # A change under 5% is noise, not a way (live: words per sentence going
    # from 9.3 to 9.2 read "worse").
    if abs(now - first) <= STEADY * max(abs(first), abs(measure.good)):
        return "steady"
    if measure.better == "band":
        mid = (measure.good + (measure.good_high or measure.good)) / 2
        return "better" if abs(now - mid) < abs(first - mid) else "worse"
    up = now > first
    return "better" if up == (measure.better == "higher") else "worse"


def _page_words(session: Session, question: Question, cache: dict) -> set[str]:
    key = (question.material_id, question.page)
    if key not in cache:
        row = session.get(MaterialPage, key)
        cache[key] = _content(row.text) if row else set()
    return cache[key]


def _one(session: Session, viva: Viva, pages: dict) -> dict[str, Any] | None:
    """One viva's numbers, or None when nothing was answered."""
    turns = _turns(session, viva.id)
    student = [t for t in turns if t.role == "student"]
    if not student:
        return None
    measures = [speaking.measure(t.text, t.timing) for t in student]
    sounded = speaking.summary(measures)
    items: list[dict[str, Any]] = []
    explains: list[bool] = []
    course_words: list[float] = []
    for q_turn in (t for t in turns if t.kind == "question" and t.question_id):
        question = session.get(Question, q_turn.question_id)
        answers = [t for t in student if t.item == q_turn.item]
        status, help_taken = _item_status(answers)
        if status == "not_answered" or question is None:
            continue
        said = " ".join(a.text for a in answers)
        items.append(
            {
                "status": status,
                "first_time": status == "correct" and not help_taken,
                "length": question.answer_length,
                "family": question.family,
                "material_id": question.material_id,
            }
        )
        if question.answer_length == "long":
            explains.append(any(speaking.framing(a.text)["reasons"] for a in answers))
        mine = _content(said)
        if len(mine) >= 3:
            course_words.append(len(mine & _page_words(session, question, pages)) / len(mine))
    course = session.get(Course, viva.course_id)
    span = span_of(session, viva)
    label = viva.scope.get("label") or ""
    if span:
        label += f" · pages {span['first']}–{span['last']}"
    answered = len(items)
    first_time = sum(i["first_time"] for i in items)
    return {
        "id": viva.id,
        "date": viva.started_at.isoformat(),
        "label": label,
        "course": course.code if course else None,
        "answered": answered,
        "items": items,
        "values": {
            "right_first_time": first_time / answered if answered else None,
            "explains": sum(explains) / len(explains) if explains else None,
            "course_words": _mean(course_words),
            "direct": sounded["direct_share"],
            "words_per_sentence": sounded["words_per_sentence"],
            "fillers_per_100": sounded["fillers_per_100"],
            "hedges_per_100": sounded["hedges_per_100"],
            "wait_ms": sounded["silence_ms_median"],
            "wpm": sounded["wpm"],
            "unfinished": (
                sounded["unfinished"] / sounded["answers"] if sounded["answers"] else None
            ),
        },
    }


FAMILY_LABEL = {
    "definition": "What a term means",
    "explain": "Why or how something works",
    "procedure": "The steps of a method",
    "observation": "What is observed",
    "application": "Where it is used",
    "numerical": "Calculations",
    "compare": "How two things differ",
    "aim": "An experiment's aim",
    "result": "An experiment's result",
    "precaution": "Precautions",
    "error": "Sources of error",
}


def _groups(vivas: list[dict[str, Any]], key: str, label: Any) -> list[dict[str, Any]]:
    counts: dict[str, list[int]] = {}
    for v in vivas:
        for item in v["items"]:
            asked_right = counts.setdefault(item[key], [0, 0])
            asked_right[0] += 1
            asked_right[1] += item["first_time"]
    out = [
        {"key": k, "label": label(k), "asked": a, "right": r, "share": round(r / a, 2)}
        for k, (a, r) in counts.items()
    ]
    return sorted(out, key=lambda g: (-g["asked"], g["label"]))


REREAD = "Your reports list these questions' pages: read them, then try the ones you missed again."


def progress(session: Session, student: str) -> dict[str, Any]:
    rows = session.exec(
        select(Viva)
        .where(Viva.student == student, Viva.status == "ended")
        .order_by(Viva.started_at)
    ).all()
    pages: dict = {}
    vivas = [v for v in (_one(session, row, pages) for row in rows) if v is not None]
    measures = []
    for m in MEASURES:
        series = [v["values"][m.key] for v in vivas]
        # Over the vivas that measured it: pace and wait exist only for spoken
        # answers, and three typed vivas in a row had made a measure taken
        # many times read "not measured yet" (live, 2026-10-29).
        taken = [value for value in series if value is not None]
        now = _mean(taken[-WINDOW:])
        first = _mean(taken[:WINDOW]) if len(taken) > WINDOW else None
        measures.append(
            {
                "key": m.key,
                "label": m.label,
                "group": m.group,
                "unit": m.unit,
                "better": m.better,
                "good": m.good,
                "fair": m.fair,
                "good_high": m.good_high,
                "fair_high": m.fair_high,
                "means": m.means,
                "tip": m.tip,
                "now": now,
                "first": first,
                "band": band(m, now),
                "direction": _direction(m, first, now),
                "series": series,
            }
        )
    by_length = _groups(
        vivas, "length", lambda k: "One-line answers" if k == "short" else "Explanations"
    )
    by_family = _groups(vivas, "family", lambda k: FAMILY_LABEL.get(k, k))
    strengths: list[dict[str, Any]] = []
    work_on: list[dict[str, Any]] = []
    for m in measures:
        said = {"kind": "measure", "key": m["key"], "text": f"{m['label']}: {_shown(m)}"}
        if m["band"] == "good":
            strengths.append(said)
        elif m["band"] == "work":
            work_on.append({**said, "tip": m["tip"]})
    for g in by_family:
        if g["asked"] < 3:
            continue
        said = {
            "kind": "questions",
            "key": g["key"],
            "text": f"{g['label']}: {g['right']} of {g['asked']} right first time",
        }
        if g["share"] >= 0.7:
            strengths.append(said)
        elif g["share"] <= 0.4:
            work_on.append({**said, "tip": REREAD})
    return {
        "vivas": len(vivas),
        "answers": sum(v["answered"] for v in vivas),
        "series": [{k: v[k] for k in ("id", "date", "label", "course", "answered")} for v in vivas],
        "measures": measures,
        "by_length": by_length,
        "by_family": by_family,
        "strengths": strengths,
        "work_on": work_on,
        # Not measured yet: said, not shown as a zero.
        "visual": {
            "measured": False,
            "planned": ["Eye contact", "Posture", "Gestures", "Facial expression"],
            "note": "Measured from the camera in a later version (the multimodal suite, M12). "
            "Nothing here is a score yet.",
        },
    }


def _shown(m: dict[str, Any]) -> str:
    value = m["now"]
    if value is None:
        return "not measured"
    if m["unit"] == "share":
        return f"{round(100 * value)}%"
    if m["unit"] == "ms":
        return f"{value / 1000:.1f} s"
    if m["unit"] == "wpm":
        return f"{round(value)} words a minute"
    return f"{round(value, 1):g}"
