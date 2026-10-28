"""The model client: three jobs (spec §6.4, §11).

    bank     ten pages of material -> viva questions, each citing its span
    marking  one answer -> which of a question's points it reached
    read     a picture of a page -> its words (reading.py), once per page

Nothing else in a viva calls a model. The examiner's lines are written by
rule, follow-ups come from the bank, and a page is banked once (Trap 8: the
free tier is 200K tokens a day per model, and a viva that generated as it
went would spend it in a handful of sessions).

A job names a TIER (`ai_core.models`), never a model; `M20_MODEL_BANK` and
`M20_MODEL_MARKING` move one job without moving the platform. Every failure
is an `LLMResult(ok=False, reason=...)`, never a raise: the bank falls back to
questions written by rule from the page, and marking to matching words —
each labelled as such.

The shape is M06's `llm.py` cut to what M20 needs; like the other copies it
belongs in `ai_core` once one of them is promoted.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai_core.models import USER_AGENT, Route, resolve

from .keys import KeyRing, load_keys

log = logging.getLogger("uvicorn.error")

JOB_BANK = "viva_bank"
JOB_MARKING = "viva_marking"
JOB_READ = "viva_read_page"


@dataclass(frozen=True)
class JobSpec:
    tier: str
    env: str
    max_tokens: int
    timeout_s: float
    temperature: float = 0.2
    #: gpt-oss spends hidden reasoning tokens before the answer.
    reasoning_effort: str | None = "low"


JOBS: dict[str, JobSpec] = {
    # Off the hot path when it can be (banked ahead of the question), so it
    # can afford the generation tier and a long budget.
    JOB_BANK: JobSpec(
        tier="generation",
        env="M20_MODEL_BANK",
        max_tokens=4000,
        timeout_s=float(os.getenv("M20_BANK_TIMEOUT", "60")),
    ),
    # On the path from an answer to the examiner's reply: bounded tightly,
    # because the rule marking is always there to answer instead.
    JOB_MARKING: JobSpec(
        tier="generation",
        env="M20_MODEL_MARKING",
        max_tokens=800,
        timeout_s=float(os.getenv("M20_MARKING_TIMEOUT", "20")),
        temperature=0.0,
    ),
    # A picture slide or a scanned page, read in the background once for
    # everyone: the vision tier (ai_core v0.42.0), word for word.
    JOB_READ: JobSpec(
        tier="vision",
        env="M20_MODEL_VISION",
        max_tokens=1500,
        timeout_s=float(os.getenv("M20_READ_TIMEOUT", "60")),
        temperature=0.0,
        reasoning_effort=None,
    ),
}

#: Request fields that are extensions to the base dialect and may be refused.
OPTIONAL_FIELDS = ("reasoning_effort", "include_reasoning")

_CALLS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="m20-llm")


@dataclass
class LLMResult:
    ok: bool = False
    data: dict[str, Any] | None = None
    reason: str | None = None
    job: str = ""
    model: str = ""
    latency_ms: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None


class LLM(Protocol):
    @property
    def available(self) -> bool: ...

    def structured(
        self, *, job: str, system: str, user: str, schema: dict[str, Any]
    ) -> LLMResult: ...

    def read_image(self, *, job: str, prompt: str, image_b64: str) -> LLMResult: ...


@dataclass
class NullLLM:
    """No key, or no route: every call says why."""

    reason: str = "no model configured"

    @property
    def available(self) -> bool:
        return False

    def structured(self, *, job: str, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        return LLMResult(ok=False, reason=self.reason, job=job)

    def read_image(self, *, job: str, prompt: str, image_b64: str) -> LLMResult:
        return LLMResult(ok=False, reason=self.reason, job=job)


def json_object(content: str) -> Any:
    """The JSON in an answer, also when wrapped in a reasoning block or a fence."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def route_for(spec: JobSpec) -> Route:
    try:
        return resolve(spec.tier, job_env=spec.env)  # type: ignore[arg-type]
    except KeyError:
        return Route(tier=spec.tier, model="", unusable=f"no {spec.tier!r} tier in ai_core")


@dataclass
class OpenAICompatLLM:
    rings: dict[str, KeyRing] = field(default_factory=dict)
    refused: dict[str, set[str]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def available(self) -> bool:
        return any(bool(route_for(spec)) for spec in JOBS.values())

    def _key(self, route: Route) -> str:
        assert route.provider is not None
        with self._lock:
            ring = self.rings.get(route.provider.name)
            if ring is None or len(ring) != len(route.keys):
                ring = KeyRing(keys=list(route.keys))
                self.rings[route.provider.name] = ring
        return ring.next()

    def _post(self, route: Route, body: dict[str, Any], timeout: float) -> tuple[Any, str | None]:
        """POST once, dropping a refused optional field and retrying a 429 or
        5xx once on the next key. Returns (payload, error)."""
        retried = False
        for _ in range(len(OPTIONAL_FIELDS) + 2):
            assert route.provider is not None
            request = urllib.request.Request(
                f"{route.provider.base_url}/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self._key(route)}",
                    "Content-Type": "application/json",
                    # A default urllib User-Agent is a Cloudflare 403 (ai_core.models).
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read()), None
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                if exc.code == 400:
                    culprit = next((f for f in OPTIONAL_FIELDS if f in body and f in detail), None)
                    if culprit is not None:
                        self.refused.setdefault(route.model, set()).add(culprit)
                        body.pop(culprit, None)
                        continue
                if (exc.code == 429 or exc.code >= 500) and not retried:
                    retried = True
                    wait = min(float(exc.headers.get("retry-after") or 1), 10.0)
                    time.sleep(wait)
                    continue
                return None, f"HTTP {exc.code}: {detail}"
            except TimeoutError:
                return None, f"timeout after {timeout:g}s"
            except Exception as exc:  # noqa: BLE001 - every failure degrades
                return None, f"{type(exc).__name__}: {exc}"
        return None, "gave up after retries"

    def can(self, job: str) -> bool:
        """Whether this job has a usable route (the vision tier may not)."""
        return bool(route_for(JOBS[job]))

    def read_image(self, *, job: str, prompt: str, image_b64: str) -> LLMResult:
        """A picture (base64 JPEG) and an instruction; the answer as text, in
        `data["text"]`."""
        spec = JOBS[job]
        route = route_for(spec)
        result = LLMResult(job=job, model=route.model)
        if not route:
            result.reason = route.unusable or "no route"
            return result
        body: dict[str, Any] = {
            "model": route.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "temperature": spec.temperature,
            "max_tokens": spec.max_tokens,
        }
        content = self._complete(spec, route, body, result)
        if content is not None:
            text = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
            result.ok, result.data = True, {"text": text}
        return result

    def _complete(
        self, spec: JobSpec, route: Route, body: dict[str, Any], result: LLMResult
    ) -> str | None:
        """Send `body`; the answer's text, or None with `result.reason` set."""
        started = time.perf_counter()
        future = _CALLS.submit(self._post, route, body, spec.timeout_s)
        try:
            payload, error = future.result(timeout=spec.timeout_s + 15)
        except FutureTimeout:
            payload, error = None, f"no answer within {spec.timeout_s:g}s"
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        if payload is None:
            result.reason = error or "no response"
            return None
        usage = payload.get("usage") or {}
        result.tokens_in, result.tokens_out = (
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
        try:
            content = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            result.reason = "response had no message content"
            return None
        if not content.strip():
            result.reason = f"empty content ({result.tokens_out} tokens, likely reasoning)"
            return None
        return content

    def structured(self, *, job: str, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        spec = JOBS[job]
        route = route_for(spec)
        result = LLMResult(job=job, model=route.model)
        if not route:
            result.reason = route.unusable or "no route"
            return result
        body: dict[str, Any] = {
            "model": route.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": spec.temperature,
            "max_tokens": spec.max_tokens,
        }
        if route.profile is not None and route.profile.reasoning and spec.reasoning_effort:
            body["reasoning_effort"] = spec.reasoning_effort
            body["include_reasoning"] = False
        if route.profile is not None and route.profile.json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": job, "strict": True, "schema": schema},
            }
        for name in self.refused.get(route.model, ()):
            body.pop(name, None)
        content = self._complete(spec, route, body, result)
        if content is None:
            return result
        try:
            parsed = json_object(content)
        except json.JSONDecodeError as exc:
            result.reason = f"unparseable JSON: {exc}"
            return result
        if not isinstance(parsed, dict):
            result.reason = "response was not a JSON object"
            return result
        result.ok, result.data = True, parsed
        return result


_llm: LLM | None = None
_llm_lock = threading.Lock()


def get_llm(*, refresh: bool = False) -> LLM:
    global _llm
    with _llm_lock:
        if _llm is not None and not refresh:
            return _llm
        load_keys()
        usable = [job for job, spec in JOBS.items() if route_for(spec)]
        if not usable:
            reason = route_for(JOBS[JOB_BANK]).unusable or "no model configured"
            log.info("M20 language model off: %s", reason)
            _llm = NullLLM(reason=reason)
        else:
            _llm = OpenAICompatLLM()
            log.info("M20 language model on for: %s", ", ".join(sorted(usable)))
        return _llm


def set_llm(llm: LLM | None) -> None:
    """Replace the client. For tests, and for nothing else."""
    global _llm
    with _llm_lock:
        _llm = llm
