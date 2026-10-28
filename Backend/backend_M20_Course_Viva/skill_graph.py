"""A viva's results reach the platform's skill graph, M04, behind the
student's consent (FR-20.20) — the way GD Arena's do
(`GD_Arena/services/ai_platform/skill_graph.py`), the shapes copied from
M04's own `ArtifactIn` and `ObservationIn`.

When a viva ends, for a student who came from the platform:

1. Their practice consent is read from M04. Without it nothing is sent, and
   the report says so.
2. Their own answers are registered as an M04 artifact, so the evidence
   resolves (M04 refuses an observation whose evidence does not).
3. One `answer_scored` observation per concept the viva's questions were on.
   The concept is found the way M04 maps a syllabus to concepts — by its own
   names and aliases (`GET /v1/concepts`) in the question, its quote and its
   points — and its outcome is the mean of those questions': right first
   time 1, right after help 0.75, partly there 0.5, otherwise 0. A question no
   concept matches is not sent (an RL deck, today: M04 has no RL concepts).
4. One on `concept:answer_structuring`, from how the answers were put
   together: opened with the answer, explanations that gave a reason.

M04 records them — dated, quoted in the skill graph's drawer — and, with no
calibrated item behind them, does not move the ability estimate (EC-4.17):
M04's call, not M20's. Best-effort and after the viva, off the student's
path: M04 being down narrows nothing here.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any

from ai_core import service as platform_service
from ai_core.models import USER_AGENT
from sqlmodel import Session

from . import speaking
from .models import Question, Viva
from .viva import _item_status, _turns

log = logging.getLogger("uvicorn.error")

M04_URL = os.getenv("M04_BASE_URL", "http://127.0.0.1:8104").rstrip("/")
TIMEOUT_S = 10.0
ARTIFACT_TYPE = "viva_answers"
#: How a viva's answers are put together: what an examiner hears as structure.
STRUCTURE = "concept:answer_structuring"
#: An answer's outcome, by how it went.
OUTCOME = {"first_time": 1.0, "correct": 0.75, "partial": 0.5}

_concepts: list[dict[str, Any]] | None = None


class Unreachable(Exception):
    """M04 did not answer, or refused."""


def _request(method: str, path: str, body: dict | None, headers: dict[str, str]) -> Any:
    """One call to M04. Replaced in tests."""
    request = urllib.request.Request(
        f"{M04_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            **headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        raise Unreachable(
            f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - M04 down is a reason, not a crash
        raise Unreachable(f"{type(exc).__name__}: {exc}") from exc


def concepts() -> list[dict[str, Any]]:
    """M04's concepts with their names and aliases, read once."""
    global _concepts
    if _concepts is None:
        found = _request("GET", "/v1/concepts", None, {})
        _concepts = [
            {
                "id": c["id"],
                "names": sorted(
                    {
                        n.casefold()
                        for n in [c.get("name", ""), *(c.get("aliases") or [])]
                        if n and len(n) >= 3
                    },
                    key=len,
                    reverse=True,
                ),
            }
            for c in (found or {}).get("concepts", [])
        ]
    return _concepts


def concept_for(question: Question, known: list[dict[str, Any]]) -> str | None:
    """The concept a question is on: the most of its names said in the
    question, its quote and its points; the longest name breaks a tie."""
    text = " ".join(
        [question.text, question.quote, *(p["point"] for p in question.answer_points)]
    ).casefold()
    best: tuple[int, int, str] | None = None
    for concept in known:
        hits = [
            n
            for n in concept["names"]
            if re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text)
        ]
        if hits:
            score = (len(hits), max(len(h) for h in hits), concept["id"])
            if best is None or score[:2] > best[:2]:
                best = score
    return best[2] if best else None


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def observations_for(
    session: Session, viva: Viva, known: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """The student's own answers (the artifact's text), and per concept the
    outcome the viva's questions on it showed."""
    turns = _turns(session, viva.id)
    answers = [t for t in turns if t.role == "student" and t.item > 0]
    per_concept: dict[str, list[float]] = {}
    for q_turn in (t for t in turns if t.kind == "question" and t.question_id):
        question = session.get(Question, q_turn.question_id)
        mine = [a for a in answers if a.item == q_turn.item]
        status, help_taken = _item_status(mine)
        if question is None or status == "not_answered":
            continue
        concept = concept_for(question, known)
        if concept is None:
            continue
        outcome = (
            OUTCOME["first_time"]
            if status == "correct" and not help_taken
            else OUTCOME.get(status, 0.0)
        )
        per_concept.setdefault(concept, []).append(outcome)
    framed = [speaking.framing(a.text) for a in answers if a.text.strip()]
    rows = [
        {"concept_id": c, "outcome": round(sum(v) / len(v), 4), "questions": len(v)}
        for c, v in sorted(per_concept.items())
    ]
    if framed and any(c["id"] == STRUCTURE for c in known):
        direct = sum(f["direct"] for f in framed) / len(framed)
        reasons = sum(1 for f in framed if f["reasons"]) / len(framed)
        rows.append(
            {"concept_id": STRUCTURE, "outcome": round((direct + reasons) / 2, 4), "questions": 0}
        )
    text = "\n".join(f"Q{a.item}: {a.text}" for a in answers if a.text.strip())
    return text, rows


def send(session: Session, viva_id: str) -> dict[str, Any]:
    """Send one ended viva's results to M04; what happened, kept on the viva
    for its report. Never raises."""
    viva = session.get(Viva, viva_id)
    done = (viva.scope or {}).get("skill_graph") if viva else None
    if viva is None or viva.status != "ended" or (done and not done.get("retry")):
        return {}
    outcome = _send(session, viva)
    viva.scope = {**viva.scope, "skill_graph": outcome}
    session.add(viva)
    session.commit()
    return outcome


def _send(session: Session, viva: Viva) -> dict[str, Any]:
    student, session_id = _uuid(viva.student), _uuid(viva.id)
    if student is None or session_id is None:
        # M04 keys students by the platform's UUID: a dev or standalone id.
        return {"sent": 0, "why": "not signed in through the platform"}
    headers = {**platform_service.headers(), "X-Candidate-Id": student, "X-Role": "student"}
    base = f"/v1/candidates/{student}"
    try:
        consents = _request("GET", f"{base}/consent?purpose=practice", None, headers) or []
        active = [c for c in consents if c.get("active")]
        if not active:
            return {"sent": 0, "why": "you have not agreed to practice being tracked"}
        text, rows = observations_for(session, viva, concepts())
        if not rows or not text:
            return {"sent": 0, "why": "none of its questions is on a concept the skill graph knows"}
        artifact = _request(
            "POST",
            f"{base}/artifacts",
            {"candidate_id": student, "session_id": session_id, "artifact_type": ARTIFACT_TYPE,
             "content": text},
            headers,
        )  # fmt: skip
        evidence = [
            {
                "kind": "artifact",
                "session_id": session_id,
                "artifact_id": artifact["artifact_id"],
                "checksum": artifact["checksum"],
            }
        ]
        batch = [
            {
                "candidate_id": student,
                "concept_id": row["concept_id"],
                "session_id": session_id,
                "evidence": evidence,
                "kind": "answer_scored",
                "response_model": "none",
                "outcome": row["outcome"],
                "source_dimension_key": "viva",
                "consent_id": active[0]["consent_id"],
            }
            for row in rows
        ]
        _request("POST", f"{base}/observations", {"observations": batch}, headers)
    except (Unreachable, KeyError, TypeError) as exc:
        log.info("M20 viva %s not sent to M04: %s", viva.id, exc)
        return {"sent": 0, "why": "the skill graph could not be reached", "retry": True}
    return {"sent": len(batch), "concepts": [row["concept_id"] for row in rows]}
