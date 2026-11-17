"""Budgeted, audited transport; fake Gemini for engineering runs; the pre-registered stopping policy.

The transport sits between the frozen hybrid-v2 client and the HTTP helper.  It sends at most one HTTP request per
client call, refuses any model other than the pre-registered one (without sending), refuses once the approved cap
is reached (without sending), and logs stage, model, outcome, HTTP-only seconds, the provider's modelVersion and
token counts - never prompt content, response text or the key.
"""
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.services.gemini_api import GeminiAPIError


class NotSent(GeminiAPIError):
    """Refused before any network activity (cap reached or wrong model)."""


class AuditedTransport:
    def __init__(self, post, log_path: Path, cap: int, model_id: str, clock: Callable[[], datetime]):
        self.post, self.log_path, self.cap, self.model_id, self.clock = post, Path(log_path), cap, model_id, clock
        self.current_case: Optional[str] = None
        self.last: Optional[dict] = None

    def rows(self) -> List[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(l) for l in self.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def sent(self) -> int:
        return len(self.rows())

    async def __call__(self, url, api_key, payload, stage, timeout, max_attempts=1):
        self.last = {"sent": False, "category": None}
        if stage != "generation" or f"/models/{self.model_id}:" not in url:
            self.last["category"] = "MODEL_MISMATCH"
            raise NotSent(stage, "MODEL_MISMATCH")
        if self.sent() >= self.cap:
            self.last["category"] = "BUDGET_EXHAUSTED"
            raise NotSent(stage, "BUDGET_EXHAUSTED")
        started, status, category, data = time.perf_counter(), "OK", None, None
        try:
            data = await self.post(url, api_key, payload, stage, timeout, max_attempts=1)
            return data
        except GeminiAPIError as exc:
            status, category = "FAILED", exc.category
            raise
        except Exception as exc:  # noqa: BLE001 - logged, then re-raised to the client, which fails closed
            status, category = "FAILED", f"UNEXPECTED_{type(exc).__name__}"
            raise
        finally:
            usage = (data or {}).get("usageMetadata") or {} if isinstance(data, dict) else {}
            row = {"n": self.sent() + 1, "case_id": self.current_case, "stage": stage, "model": self.model_id,
                   "status": status, "category": category, "http_seconds": round(time.perf_counter() - started, 3),
                   "model_version": (data or {}).get("modelVersion") if isinstance(data, dict) else None,
                   "prompt_tokens": usage.get("promptTokenCount"), "output_tokens": usage.get("candidatesTokenCount"),
                   "thinking_tokens": usage.get("thoughtsTokenCount"), "total_tokens": usage.get("totalTokenCount"),
                   "at": self.clock().isoformat()}
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
            self.last = {"sent": True, "category": category}


# ------------------------------------------------------------------ fake Gemini (engineering only)
def _body(recommendation: str, concerns: List[dict], red_flags: Optional[List[str]] = None) -> dict:
    return {"authenticity_score": 70 if recommendation == "AUTO_APPROVE" else 45,
            "risk_level": "LOW" if recommendation == "AUTO_APPROVE" else "HIGH" if recommendation in ("FLAG_FOR_REVIEW", "REJECT") else "MEDIUM",
            "recommendation": recommendation, "summary": "Scripted engineering response (not a model output).",
            "dimension_scores": {"plausibility": 70, "specificity": 70, "red_flag_score": 70, "documentation": 70},
            "red_flags": red_flags or [], "positive_signals": [], "missing_requirements": [], "concerns": concerns}


class ScriptedGemini:
    """Deterministic stand-in for the API.  script[case_id] is a list of steps, one per request for that case:
    approve | nmi | flag_grounded | flag_ungrounded | reject_ungrounded | invalid_json | truncated |
    SERVER_ERROR | READ_TIMEOUT | QUOTA_EXHAUSTED | AUTHENTICATION | RATE_LIMIT ...  The last step repeats."""

    def __init__(self, script: Dict[str, List[str]], cases: Dict[str, dict], transport_ref: "AuditedTransport"):
        self.script, self.cases, self.ref = script, cases, transport_ref

    async def __call__(self, url, api_key, payload, stage, timeout, max_attempts=1):
        case_id = self.ref.current_case
        steps = self.script.get(case_id, ["approve"])
        previous = sum(r["case_id"] == case_id for r in self.ref.rows())     # persisted, so resumes continue the script
        step = steps[min(previous, len(steps) - 1)]
        status = {"SERVER_ERROR": 503, "QUOTA_EXHAUSTED": 429, "RATE_LIMIT": 429, "AUTHENTICATION": 401,
                  "MODEL_NOT_FOUND": 404, "BAD_REQUEST": 400}
        if step in status or step.endswith("TIMEOUT"):
            raise GeminiAPIError(stage, step, status.get(step))
        document = (self.cases.get(case_id, {}).get("input", {}).get("documents") or [{}])[0]
        quote = " ".join((document.get("content") or "").split()[:12])
        bodies = {
            "approve": _body("AUTO_APPROVE", []),
            "nmi": _body("NEEDS_MORE_INFO", [{"category": "MISSING_INFORMATION", "description": "A cost document is needed."}]),
            "flag_grounded": _body("FLAG_FOR_REVIEW", [{"category": "CONTRADICTION", "description": "Documents disagree.",
                                                        "document_title": document.get("title", ""), "evidence_quote": quote}]),
            "flag_ungrounded": _body("FLAG_FOR_REVIEW", [{"category": "SUSPECTED_FRAUD", "description": "This looks fabricated."}]),
            "reject_ungrounded": _body("REJECT", [{"category": "SUSPECTED_FRAUD", "description": "Likely a scam."}]),
        }
        usage = {"promptTokenCount": len(json.dumps(payload)) // 4, "candidatesTokenCount": 300, "totalTokenCount": 0}
        if step == "invalid_json":
            text, finish = "{not json", "STOP"
        elif step == "truncated":
            text, finish = json.dumps(bodies["approve"]), "MAX_TOKENS"
        else:
            text, finish = json.dumps(bodies[step]), "STOP"
        return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}],
                "modelVersion": "engineering-fake", "usageMetadata": usage}


# ------------------------------------------------------------------ stopping policy
@dataclass
class Action:
    kind: str                       # CONTINUE | RETRY | PAUSE | STOP
    reason: str = ""
    resume_not_before: Optional[str] = None


@dataclass
class PolicyState:
    started_at: str
    paused_until: Optional[str] = None
    transient_pauses: Dict[str, int] = field(default_factory=dict)      # UTC date -> pauses that day
    retries_used: int = 0
    stopped: Optional[str] = None
    pause_reason: Optional[str] = None


class StopPolicy:
    """Operational stopping rules from the pre-registration.  Decisions never depend on case outcomes."""

    def __init__(self, rules: dict, cap: int, retry_allowance: int, state: PolicyState, max_retries_per_case: int = 1):
        self.r, self.cap, self.allowance, self.state = rules, cap, retry_allowance, state
        self.max_retries = max_retries_per_case

    def classify(self, category: Optional[str]) -> str:
        if category is None:
            return "ok"
        if category in self.r["stop_categories"]:
            return "stop"
        if category in self.r["pause_categories"]:
            return "quota"
        if category in self.r["transient_categories"]:
            return "transient"
        return "invalid_output"          # parsed but unusable: final for the case, never retried

    def before_request(self, now: datetime, sent: int) -> Action:
        if self.state.stopped:
            return Action("STOP", self.state.stopped)
        if sent >= self.cap:
            return self._stop("CALL_LIMIT_REACHED")
        if now - datetime.fromisoformat(self.state.started_at) >= timedelta(days=self.r["calendar_limit_days"]):
            return self._stop("CALENDAR_LIMIT_REACHED")
        if self.state.paused_until and now < datetime.fromisoformat(self.state.paused_until):
            return Action("PAUSE", self.state.pause_reason or "PAUSED", self.state.paused_until)
        return Action("CONTINUE")

    def after_request(self, now: datetime, history: List[Optional[str]], case_attempts: int) -> Action:
        """`history`: categories of every sent request so far (this one last).  `case_attempts`: sent, non-quota
        requests for the current case, including this one."""
        kind = self.classify(history[-1])
        if kind == "stop":
            return self._stop(f"CONFIGURATION_ERROR:{history[-1]}")
        if kind == "quota":
            reset = now.replace(hour=self.r.get("quota_reset_utc_hour", 8), minute=0, second=0, microsecond=0)
            if reset <= now:
                reset += timedelta(days=1)
            return self._pause("QUOTA_EXHAUSTED", reset)
        transient = [self.classify(c) == "transient" for c in history if self.classify(c) != "quota"]
        if len(transient) >= self.r["stop_cumulative_min_requests"] and \
                sum(transient) / len(transient) > self.r["stop_cumulative_transient_share"]:
            return self._stop("TRANSIENT_FAILURE_RATE_EXCEEDED")
        if kind != "transient":
            return Action("CONTINUE")
        consecutive = 0
        for flag in reversed(transient):
            if not flag:
                break
            consecutive += 1
        window = transient[-self.r["pause_window_requests"]:]
        windowed = len(window) >= self.r["pause_window_requests"] and \
            sum(window) / len(window) > self.r["pause_window_transient_share"]
        if consecutive >= self.r["pause_after_consecutive_transient"] or windowed:
            return self._transient_pause(now, "CONSECUTIVE_TRANSIENT_FAILURES" if not windowed else "TRANSIENT_FAILURE_WINDOW")
        if case_attempts > self.max_retries:      # this case already had its retry: the failure is final
            return Action("CONTINUE", "RETRY_ALREADY_USED")
        return Action("RETRY", "TRANSIENT_FAILURE")

    def claim_retry(self) -> Action:
        """Called before sending a case's retry (immediately or after a pause)."""
        if self.state.retries_used >= self.allowance:
            if self.r["stop_when_retry_allowance_used"]:
                return self._stop("RETRY_ALLOWANCE_USED")
            return Action("CONTINUE", "NO_RETRY_LEFT")
        self.state.retries_used += 1
        return Action("RETRY")

    def _transient_pause(self, now: datetime, reason: str) -> Action:
        day = now.date().isoformat()
        self.state.transient_pauses[day] = self.state.transient_pauses.get(day, 0) + 1
        if self.state.transient_pauses[day] >= self.r["max_transient_pauses_per_utc_day"]:
            until = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            return self._pause(reason + "_DAILY_LIMIT", until)
        return self._pause(reason, now + timedelta(minutes=self.r["pause_minutes"]))

    def _pause(self, reason: str, until: datetime) -> Action:
        self.state.paused_until, self.state.pause_reason = until.isoformat(), reason
        return Action("PAUSE", reason, until.isoformat())

    def _stop(self, reason: str) -> Action:
        self.state.stopped = reason
        return Action("STOP", reason)
