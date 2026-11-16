"""Controlled development-only evaluation of the frozen date-aware Gemini prompt (hybrid v2).

Protocol: evaluation/date_aware_dev_eval/PREREGISTRATION.md (hashes recorded in prereg_manifest.json).

  check     render the 8 new scenarios for today's Asia/Kolkata date, run every pre-flight check and print the
            call plan.  No network.
  register  write prereg_manifest.json (hashes of the scenarios, protocol, runner and tests).  No network.
  dry-run   the whole pipeline with a fake Gemini transport into --output-dir.  No network.
  execute   the one live run.  Requires SEVAFUND_GEMINI_EVAL_APPROVED=1 and GEMINI_MODEL=gemini-3.6-flash in the
            process environment, --max-calls <= 10, a valid hybrid-v2 freeze and a committed, unchanged
            pre-registration.  --resume continues a run stopped by a quota / rate limit inside the same budget.
  analyze   recompute every decision, metric and safety check from a run directory.  No network.

Systems compared on identical rendered cases
  A   frozen V3 alone (offline)
  B   existing V3 + Gemini: production prompt + frozen existing escalation rule   (live on 2 pre-registered cases)
  C   improved V3 + Gemini: frozen date-aware prompt + frozen hybrid-v2 policy    (live on all 8 cases)
  B'  ablation, NOT system B: the existing escalation rule applied to C's Gemini output (no call)
"""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_evaluation_framework as fw  # noqa: E402
from freeze_hybrid_v2 import verify as verify_freeze  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.development_approval_workflow import AutomatedOutcome, start  # noqa: E402
from app.services.development_approval_workflow.schemas import (  # noqa: E402
    ConfirmationCheck, ConfirmationOutcome, ConfirmationRecord, ContactSource, WorkflowState)
from app.services.development_approval_workflow.workflow import record_confirmation  # noqa: E402
from app.services.development_gemini_verification import (  # noqa: E402
    assess_dates, build_concerns, combine, verify_with_gemini)
from app.services.development_gemini_verification.dates import claims_future_date  # noqa: E402
from app.services.development_verifier_v3 import verify_case  # noqa: E402
from app.services.gemini_api import GeminiAPIError  # noqa: E402
from evaluate_development_verifier_v3 import v3_input  # noqa: E402

HERE = Path(__file__).resolve().parent
KIT = HERE / "date_aware_dev_eval"
SCENARIOS = KIT / "scenarios.json"
PREREG = KIT / "PREREGISTRATION.md"
PREREG_MANIFEST = KIT / "prereg_manifest.json"
LIVE_DIR = HERE / "runs" / "date_aware_dev_eval_live"
REGISTERED_FILES = ["evaluation/date_aware_dev_eval/scenarios.json", "evaluation/date_aware_dev_eval/PREREGISTRATION.md",
                    "evaluation/run_date_aware_dev_eval.py", "tests/test_date_aware_dev_eval.py"]

IST = ZoneInfo("Asia/Kolkata")
MODEL = "gemini-3.6-flash"
PRODUCTION_DEFAULT_LINE = 'GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")'
APPROVED_CALL_LIMIT = 10
B_CASES = ["DA-01", "DA-06"]           # pre-registered paired production-prompt cases, in this order
MAX_TRANSIENT_FAILURES = 1             # a second timeout / server error stops the run for good
MAX_TRANSIENT_RETRIES = 1
RESUMABLE = {"QUOTA_EXHAUSTED", "RATE_LIMIT", "RESOURCE_EXHAUSTED"}
DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}
DISTINCT_MAX_JACCARD = 0.20            # word-trigram Jaccard against every earlier case
PRIOR_SOURCES = ["evaluation/*.jsonl", "evaluation/gemini_eval_v1/cases.jsonl", "evaluation/independent_test_v4/*.json"]


# ------------------------------------------------------------------ scenarios
def reference_date(now: Optional[datetime] = None) -> date:
    """Today's date in Asia/Kolkata (never hard-coded; never the machine's or UTC's date)."""
    return (now or datetime.now(timezone.utc)).astimezone(IST).date()


_PLACEHOLDER = re.compile(r"\{\{d([+-]\d+)\|(dmy|dmyh|long|short|iso)\}\}")


def _fmt(value: date, style: str) -> str:
    return {"dmy": value.strftime("%d/%m/%Y"), "dmyh": value.strftime("%d-%m-%Y"),
            "long": f"{value.day} {value.strftime('%B %Y')}", "short": f"{value.day} {value.strftime('%b %Y')}",
            "iso": value.isoformat()}[style]


def render(text: str, ref: date) -> str:
    return _PLACEHOLDER.sub(lambda m: _fmt(ref + timedelta(days=int(m.group(1))), m.group(2)), text)


def render_cases(ref: date, spec: Optional[dict] = None) -> List[dict]:
    spec = spec or json.loads(SCENARIOS.read_text(encoding="utf-8"))
    cases = []
    for s in spec["scenarios"]:
        data = json.loads(json.dumps(s["input"]))
        data["title"], data["story"] = render(data["title"], ref), render(data["story"], ref)
        data["documents"] = [dict(d, content=render(d["content"], ref)) for d in data["documents"]]
        data["submitted_on"] = ref.isoformat()
        cases.append({"case_id": s["case_id"], "ground_truth": s["ground_truth"], "scenario_type": s["scenario_type"],
                      "scenario_family": s["scenario_family"], "synthetic": True, "expected": s["expected"],
                      "scenario_checks": s["safety_checks"], "input": data})
    if "{{" in json.dumps(cases):
        raise ValueError("unrendered date placeholder")
    return cases


def evidence(case: dict) -> List[dict]:
    """Frozen lexical top-5 retrieval (production's no-embedding path).  Every case has <= 5 chunks, so top-5
    embedding retrieval would return the same chunks; only their order and relevance numbers differ."""
    return fw.lexical_retrieve(case, top_k=5)


def coverage(case: dict) -> dict:
    total, got = fw._documents_as_chunks(case), evidence(case)
    return {"chunks": len(total), "retrieved": len(got), "complete": len(total) <= 5 and len(got) == len(total)}


# -------------------------------------------------------------- distinctness
def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").casefold())


def _case_text(data: dict) -> str:
    return " ".join([data.get("title", ""), data.get("story", ""), data.get("beneficiary_name") or ""]
                    + [d.get("content", "") for d in data.get("documents", [])])


def _trigrams(text: str) -> set:
    t = _tokens(text)
    return {tuple(t[i:i + 3]) for i in range(len(t) - 2)}


def prior_cases() -> List[dict]:
    rows = []
    for pattern in PRIOR_SOURCES:
        for path in sorted(ROOT.glob(pattern)):
            text = path.read_text(encoding="utf-8")
            items = [json.loads(text)] if path.suffix == ".json" else [json.loads(l) for l in text.splitlines() if l.strip()]
            for item in items:
                data = item.get("input", item)
                if isinstance(data, dict) and (data.get("story") or data.get("documents")):
                    rows.append({"source": str(path.relative_to(ROOT)), "case_id": item.get("case_id"),
                                 "text": _case_text(data)})
    return rows


def distinctness(cases: List[dict]) -> dict:
    priors = prior_cases()
    prior_grams = [(p, _trigrams(p["text"])) for p in priors]
    corpus = " ".join(" ".join(_tokens(p["text"])) for p in priors)
    out = {"prior_cases_compared": len(priors), "threshold_max_jaccard": DISTINCT_MAX_JACCARD, "cases": {}}
    for case in cases:
        grams = _trigrams(_case_text(case["input"]))
        best, best_id = 0.0, None
        for prior, pg in prior_grams:
            score = len(grams & pg) / len(grams | pg) if grams | pg else 0.0
            if score > best:
                best, best_id = score, f"{prior['source']}:{prior['case_id']}"
        names = [case["input"]["beneficiary_name"]] + [d["content"].split("\n")[0] for d in case["input"]["documents"]]
        shared = sorted({n for n in names if " ".join(_tokens(n)) and f" {' '.join(_tokens(n))} " in f" {corpus} "})
        out["cases"][case["case_id"]] = {"max_trigram_jaccard": round(best, 4), "closest_prior_case": best_id,
                                         "names_found_in_prior_data": shared,
                                         "distinct": best <= DISTINCT_MAX_JACCARD and not shared}
    out["all_distinct"] = all(c["distinct"] for c in out["cases"].values())
    return out


# ------------------------------------------------------------------ checks
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_unchanged() -> dict:
    freeze = verify_freeze()
    config_text = (ROOT / "app/config.py").read_text(encoding="utf-8")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "app/"], capture_output=True, text=True,
                           cwd=ROOT).stdout.strip()
    return {"hybrid_v2_freeze_valid": freeze["valid"], "freeze_changed": freeze["changed"], "freeze_added": freeze["added"],
            "production_default_model_is_3_8": PRODUCTION_DEFAULT_LINE in config_text,
            "uncommitted_changes_under_app": bool(dirty)}


def preregistration_status() -> dict:
    if not PREREG_MANIFEST.exists():
        return {"registered": False, "matches": False, "committed": False}
    manifest = json.loads(PREREG_MANIFEST.read_text())
    now = {p: _sha(ROOT / p) for p in REGISTERED_FILES}
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", *REGISTERED_FILES, str(PREREG_MANIFEST.relative_to(ROOT))],
                             capture_output=True, text=True, cwd=ROOT).returncode == 0
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *REGISTERED_FILES,
                            str(PREREG_MANIFEST.relative_to(ROOT))], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return {"registered": True, "matches": now == manifest["files"], "committed": tracked and not dirty,
            "registered_at_utc": manifest["registered_at_utc"]}


def preflight(cases: List[dict]) -> dict:
    labels = Counter(c["ground_truth"] for c in cases)
    cov = {c["case_id"]: coverage(c) for c in cases}
    dist = distinctness(cases)
    prod = production_unchanged()
    problems = []
    if len(cases) != 8 or labels != Counter({"fraudulent": 4, "legitimate": 4}):
        problems.append(f"expected 8 cases, 4 fraudulent / 4 legitimate; got {dict(labels)}")
    if not all(v["complete"] for v in cov.values()):
        problems.append("retrieval would not include every chunk for some case")
    if not dist["all_distinct"]:
        problems.append("a scenario is too similar to an earlier case")
    if not prod["hybrid_v2_freeze_valid"]:
        problems.append("the hybrid-v2 freeze does not verify")
    if not prod["production_default_model_is_3_8"]:
        problems.append("the production default model line in app/config.py changed")
    if prod["uncommitted_changes_under_app"]:
        problems.append("uncommitted changes under app/")
    return {"ok": not problems, "problems": problems, "labels": dict(labels), "retrieval_coverage": cov,
            "distinctness": dist, "production": prod}


def call_plan() -> dict:
    return {"model": MODEL, "approved_call_limit": APPROVED_CALL_LIMIT, "embedding_calls": 0,
            "phase_1": "C (date-aware prompt) on DA-01..DA-08, one generation request each (8)",
            "phase_2": f"at most {MAX_TRANSIENT_RETRIES} retry of a C request that failed with a timeout/server error",
            "phase_3": f"B (production prompt) on {B_CASES} in that order with the remaining budget",
            "stop_rules": ["quota / rate-limit / auth / model-not-found / budget error: stop (quota or rate limit may "
                           "be resumed later inside the same 10-request budget)",
                           f"more than {MAX_TRANSIENT_FAILURES} timeout/server error: stop for good",
                           "a request that fails for any other reason (bad JSON, truncated, blocked) is final and is "
                           "scored fail-closed; it is not retried"],
            "http_requests_per_call": 1, "pacing_seconds": 6.0}


# ------------------------------------------------------------------ transports
class AuditedPost:
    """Counts and logs every real HTTP request (stage, model, outcome, seconds) - never content or the key."""

    def __init__(self, post, log_path: Path):
        self.post, self.log_path = post, log_path

    def rows(self) -> List[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text().splitlines() if line.strip()]

    def count(self) -> int:
        return len(self.rows())

    async def __call__(self, url, api_key, payload, stage, timeout_seconds, max_attempts=1):
        started, status, category = time.perf_counter(), "OK", None
        try:
            return await self.post(url, api_key, payload, stage, timeout_seconds, max_attempts=max_attempts)
        except GeminiAPIError as exc:
            status, category = "FAILED", exc.category
            raise
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            status, category = "FAILED", f"UNEXPECTED_{type(exc).__name__}"
            raise
        finally:
            model = re.search(r"models/([^:/]+):", url)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"n": self.count() + 1, "stage": stage, "model": model.group(1) if model else None,
                                         "status": status, "category": category,
                                         "seconds": round(time.perf_counter() - started, 3),
                                         "at": datetime.now(timezone.utc).isoformat()}) + "\n")


class FakeGemini:
    """Deterministic stand-in for the Gemini API (dry runs and tests).  `failures` maps the n-th request to a
    (category, status) pair raised as GeminiAPIError; other requests get a schema-valid NEEDS_MORE_INFO answer."""

    def __init__(self, failures: Optional[Dict[int, tuple]] = None, recommendation: str = "NEEDS_MORE_INFO"):
        self.failures, self.recommendation, self.requests = failures or {}, recommendation, 0

    async def __call__(self, url, api_key, payload, stage, timeout_seconds, max_attempts=1):
        self.requests += 1
        if self.requests in self.failures:
            category, status = self.failures[self.requests]
            raise GeminiAPIError(stage, category, status)
        dated = "concerns" in payload["generationConfig"]["responseSchema"]["properties"]
        body = {"authenticity_score": 55, "risk_level": "MEDIUM", "recommendation": self.recommendation,
                "summary": "Fake response for an offline dry run.",
                "dimension_scores": {"plausibility": 60, "specificity": 60, "red_flag_score": 70, "documentation": 50},
                "red_flags": ["Independent confirmation of the institution is pending."], "positive_signals": [],
                "missing_requirements": ["Independent confirmation of the institution"]}
        if dated:
            body["concerns"] = [{"category": "MISSING_INFORMATION",
                                 "description": "Independent confirmation of the institution is pending."}]
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(body)}]}}]}


# ------------------------------------------------------------------ execution
class RunLog:
    def __init__(self, directory: Path):
        self.directory = directory
        self.attempts_path, self.outputs_path = directory / "attempts.jsonl", directory / "outputs.jsonl"

    def _read(self, path: Path) -> List[dict]:
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def attempts(self) -> List[dict]:
        return self._read(self.attempts_path)

    def outputs(self) -> List[dict]:
        return self._read(self.outputs_path)

    def append(self, path: Path, row: dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")

    def history(self, system: str, case_id: str, requests_only: bool = False) -> List[str]:
        """Outcomes in order.  requests_only drops attempts that never reached the API (e.g. budget exhausted)."""
        return [a["category"] or "OK" for a in self.attempts() if a["system"] == system and a["case_id"] == case_id
                and (a["http_requests"] or not requests_only)]

    def transient_failures(self) -> int:
        return sum(a["category"] in fw.TRANSIENT_FAILURES for a in self.attempts())

    def transient_retries(self) -> int:
        return sum(bool(a.get("transient_retry")) for a in self.attempts())

    def final_stop(self) -> Optional[str]:
        for a in self.attempts():
            if a.get("stop") and a["stop"] not in RESUMABLE:
                return a["stop"]
        return None


def next_job(log: RunLog, order: List[str]) -> Optional[tuple]:
    for case_id in order:                                    # phase 1 (and quota-stopped requests on resume)
        h = log.history("C", case_id)
        if not h or h[-1] in RESUMABLE:
            return ("C", case_id, False)
    if log.transient_retries() < MAX_TRANSIENT_RETRIES:      # phase 2
        for case_id in order:
            h = log.history("C", case_id)
            if h and h[-1] in fw.TRANSIENT_FAILURES and sum(x in fw.TRANSIENT_FAILURES for x in h) == 1:
                return ("C", case_id, True)
    for case_id in B_CASES:                                  # phase 3
        h = log.history("B", case_id)
        if not h or h[-1] in RESUMABLE:
            return ("B", case_id, False)
    return None


async def run_jobs(cases: List[dict], transport: fw.BudgetedTransport, audit: AuditedPost, log: RunLog) -> dict:
    by_id = {c["case_id"]: c for c in cases}
    order = [c["case_id"] for c in cases]
    stop = None
    while stop is None:
        job = next_job(log, order)
        if job is None:
            break
        system, case_id, retry = job
        case = by_id[case_id]
        before, started = audit.count(), time.perf_counter()
        category, status_code, record = None, None, None
        try:
            if system == "C":
                record = await fw.run_gemini_dated(case, evidence(case), transport)
            else:
                record = await fw.run_gemini(case, evidence(case), transport)
        except GeminiAPIError as exc:
            category, status_code = exc.category, exc.status_code
        except Exception as exc:  # noqa: BLE001 - any other failure is scored fail-closed
            category = f"UNEXPECTED_{type(exc).__name__}"
        row = {"system": system, "case_id": case_id, "status": "OK" if category is None else "FAILED",
               "category": category, "status_code": status_code, "http_requests": audit.count() - before,
               "wall_seconds": round(time.perf_counter() - started, 3),
               "http_seconds": round(sum(h["seconds"] for h in audit.rows()[before:]), 3) if audit.count() > before else None,
               "transient_retry": retry,
               "at": datetime.now(timezone.utc).isoformat()}
        if category in fw.STOP_CATEGORIES:
            stop = category
        elif category in fw.TRANSIENT_FAILURES and log.transient_failures() + 1 > MAX_TRANSIENT_FAILURES:
            stop = "EARLY_STOP_TRANSIENT_FAILURES"
        row["stop"] = stop
        log.append(log.attempts_path, row)
        if record is not None:
            log.append(log.outputs_path, {"system": system, "case_id": case_id, "record": record})
    return {"stopped_reason": stop, "http_requests_total": audit.count(), "attempts": len(log.attempts())}


def make_transport(post, api_key: str, run_dir: Path, pacing: float) -> tuple:
    audit = AuditedPost(post, run_dir / "http_requests.jsonl")
    used = audit.count()
    transport = fw.BudgetedTransport(audit, api_key, APPROVED_CALL_LIMIT, pacing,
                                     stage_limits={"generation": APPROVED_CALL_LIMIT, "embedding": 0},
                                     already_used=Counter({"generation": used}))
    return transport, audit


def start_run(run_dir: Path, ref: date, mode: str) -> List[dict]:
    cases = render_cases(ref)
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "rendered_cases.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases),
                                                   encoding="utf-8")
    manifest = {"mode": mode, "started_utc": datetime.now(timezone.utc).isoformat(),
                "reference_date_asia_kolkata": ref.isoformat(),
                "utc_date_at_start": datetime.now(timezone.utc).date().isoformat(),
                "model": MODEL if mode == "live" else "fake", "call_plan": call_plan(),
                "scenarios_sha256": _sha(SCENARIOS), "preregistration": preregistration_status(),
                "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                           cwd=ROOT).stdout.strip(),
                "production": production_unchanged()}
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return cases


def load_run_cases(run_dir: Path) -> List[dict]:
    return [json.loads(l) for l in (run_dir / "rendered_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


# ------------------------------------------------------------------ analysis
FAILURE_INJECTIONS = {
    "READ_TIMEOUT": {"exc": ("READ_TIMEOUT", None)}, "SERVER_ERROR_503": {"exc": ("SERVER_ERROR", 503)},
    "QUOTA_EXHAUSTED_429": {"exc": ("QUOTA_EXHAUSTED", 429)}, "RATE_LIMIT_429": {"exc": ("RATE_LIMIT", 429)},
    "AUTHENTICATION_401": {"exc": ("AUTHENTICATION", 401)}, "EMPTY_CANDIDATES": {"response": {"candidates": []}},
    "TRUNCATED": {"response": {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]}},
    "BLOCKED": {"response": {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}},
    "MALFORMED_JSON": {"response": {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not json"}]}}]}},
    "SCHEMA_INVALID": {"response": {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": json.dumps({"recommendation": "AUTO_APPROVE"})}]}}]}},
    "UNEXPECTED_EXCEPTION": {"raise": True}, "NOT_CONFIGURED": {"no_key": True},
}
_UNGROUNDED = "The supporting paperwork could be forged."
MODEL_INJECTIONS = {
    "GEMINI_APPROVES_CLEAN": {"decision": "APPROVED", "concerns": []},
    "GEMINI_REJECTS_UNGROUNDED": {"decision": "REJECTED", "concerns": [
        {"category": "SUSPECTED_FRAUD", "description": "This campaign is a scam.", "evidence_quote": ""}]},
    "GEMINI_FLAGS_UNGROUNDED": {"decision": "FLAG_FOR_REVIEW", "concerns": [
        {"category": "SUSPECTED_FRAUD", "description": "This campaign is a scam.", "evidence_quote": ""}]},
    "UNGROUNDED_WARNING_WITH_INFO_REQUEST": {"decision": "NEEDS_MORE_INFORMATION", "concerns": [
        {"category": "SUSPECTED_FRAUD", "description": _UNGROUNDED, "evidence_quote": ""}]},
    "UNGROUNDED_WARNING_WITH_APPROVAL": {"decision": "APPROVED", "concerns": [
        {"category": "SUSPECTED_FRAUD", "description": _UNGROUNDED, "evidence_quote": ""}]},
    "UNGROUNDED_FREE_TEXT_WARNING": {"decision": "NEEDS_MORE_INFORMATION", "concerns": [],
                                     "red_flag_texts": ["Possible fraud: the paperwork may be forged."]},
    "FUTURE_DATE_CLAIM_WITH_INFO_REQUEST": {"decision": "NEEDS_MORE_INFORMATION", "concerns": [
        {"category": "DATE_ISSUE", "description": "The documents are future-dated."}]},
    "FUTURE_DATE_CLAIM_WITH_APPROVAL": {"decision": "APPROVED", "concerns": [
        {"category": "DATE_ISSUE", "description": "The documents are future-dated."}]},
}
INDEPENDENT_BASIS = {"V3_CONTRADICTION", "FUTURE_DATED_DOCUMENT"}   # escalations that do not come from Gemini


def _injected_transport(spec: dict):
    async def post(url, api_key, payload, stage, timeout_seconds, max_attempts=1):
        if "exc" in spec:
            raise GeminiAPIError(stage, *spec["exc"])
        if spec.get("raise"):
            raise RuntimeError("injected")
        return spec["response"]
    return post


def _context(case: dict) -> dict:
    data = case["input"]
    ref = date.fromisoformat(data["submitted_on"])
    v3 = verify_case(v3_input(data))
    dates = assess_dates([(d.get("title", ""), d.get("content", "")) for d in data.get("documents", [])], ref)
    campaign_text = " ".join(str(data.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state"))
    return {"data": data, "ref": ref, "v3": v3, "dates": dates, "campaign_text": campaign_text, "chunks": evidence(case)}


def _combine(ctx: dict, gemini: Optional[dict]):
    return combine(ctx["v3"].decision.value, gemini, ctx["chunks"], ctx["campaign_text"], ctx["dates"],
                   category=ctx["data"]["category"], beneficiary_type=ctx["data"].get("beneficiary_type"),
                   v3_information_requests=ctx["v3"].information_requests)


def _workflow(ctx: dict, decision: str):
    return start(AutomatedOutcome(decision=decision, category=ctx["data"]["category"],
                                  beneficiary_type=ctx["data"].get("beneficiary_type")))


def confirmation_simulation(ctx: dict) -> dict:
    """What external confirmation does to a campaign that automated checks made eligible (forced APPROVED)."""
    def fresh():
        return _workflow(ctx, "APPROVED")

    def confirm(record, check, source=ContactSource.OFFICIAL_DIRECTORY, outcome=ConfirmationOutcome.CONFIRMED):
        return record_confirmation(record, ConfirmationRecord(check=check, outcome=outcome, contact_source=source,
                                                              verifier_id="sim"), ctx["campaign_text"])
    checks = [ConfirmationCheck.BENEFICIARY, ConfirmationCheck.PAYMENT_DESTINATION, ConfirmationCheck.INSTITUTION]
    out = {}
    record = fresh()
    out["required_checks"] = sorted(r.check.value for r in record.required_confirmations)
    out["no_confirmation_disbursement_allowed"] = record.disbursement_allowed
    record = fresh()
    for check in checks:
        record = confirm(record, check, ContactSource.CAMPAIGN_SUPPLIED)
    out["campaign_supplied_contacts_state"] = record.state.value
    record = fresh()
    for check in checks[:2]:
        record = confirm(record, check)
    out["institution_unconfirmed_state"] = record.state.value
    record = fresh()
    record = confirm(record, ConfirmationCheck.INSTITUTION, outcome=ConfirmationOutcome.CONTRADICTED)
    out["institution_contradicts_state"] = record.state.value
    record = fresh()
    for check in checks:
        record = confirm(record, check)
    out["all_independent_state"] = record.state.value          # positive control: the path to activation exists
    out["mandatory"] = (not out["no_confirmation_disbursement_allowed"]
                        and out["campaign_supplied_contacts_state"] != "VERIFIED_ACTIVE"
                        and out["institution_unconfirmed_state"] != "VERIFIED_ACTIVE"
                        and out["institution_contradicts_state"] == "FLAG_FOR_REVIEW"
                        and set(out["required_checks"]) == {c.value for c in checks})
    return out


def injections(case: dict, ctx: dict) -> dict:
    out = {"api_failures": {}, "model_outputs": {}}
    for name, spec in FAILURE_INJECTIONS.items():
        outcome = asyncio.run(verify_with_gemini(
            ctx["data"], ctx["chunks"], ctx["ref"], ctx["ref"], transport=_injected_transport(spec),
            api_key="" if spec.get("no_key") else "injected-test-key", model=MODEL))
        result = _combine(ctx, outcome.model_dump())
        out["api_failures"][name] = {"gemini_status": outcome.status, "failure_category": outcome.failure_category,
                                     "decision": result.decision, "state": result.workflow_state,
                                     "trigger": result.triggers[0]}
    for name, spec in MODEL_INJECTIONS.items():
        gemini = {"status": "OK", "red_flag_texts": [], "missing_requirements": [], **spec}
        result = _combine(ctx, gemini)
        out["model_outputs"][name] = {"decision": result.decision, "state": result.workflow_state,
                                      "trigger": result.triggers[0], "vetoed": result.vetoed_concerns,
                                      "unverified": result.unverified_concerns}
    return out


def _concern_rows(gemini: dict, ctx: dict) -> List[dict]:
    concerns = build_concerns(gemini, ctx["chunks"], ctx["campaign_text"], ctx["dates"])
    return [{"text": c.text, "type": c.type, "source": c.source, "document": c.document,
             "evidence_quote": c.evidence_quote, "grounded": c.grounded, "vetoed": c.vetoed,
             "veto_reason": c.veto_reason, "escalates": c.escalates} for c in concerns]


def _future_claims(record: dict) -> List[str]:
    texts = [record.get("summary") or ""] + list(record.get("red_flag_texts") or []) + \
            [c.get("description", "") for c in record.get("concerns") or []]
    return [t for t in texts if claims_future_date(t)]


def analyze_case(case: dict, c_out: Optional[dict], c_fail: Optional[str], b_out: Optional[dict],
                 b_fail: Optional[str], b_attempted: bool) -> dict:
    ctx = _context(case)
    v3 = ctx["v3"].decision.value
    row = {"case_id": case["case_id"], "scenario_type": case["scenario_type"], "label": case["ground_truth"],
           "expected": case["expected"], "scenario_checks": case["scenario_checks"],
           "reference_date": ctx["ref"].isoformat(),
           "document_dates": [f"{d.document}: {d.raw} [{d.kind}] {d.status}" for d in ctx["dates"].dates],
           "future_dated_documents": [d.document for d in ctx["dates"].future],
           "expired_documents": [d.document for d in ctx["dates"].expired]}
    row["A"] = {"decision": v3, "state": _workflow(ctx, v3).state.value, "reasons": ctx["v3"].reasons[:4],
                "information_requests": ctx["v3"].information_requests[:4],
                "finding_codes": sorted({f.code for f in ctx["v3"].findings})}
    # C - improved V3 + Gemini (fail-closed when the call failed)
    if c_out is not None:
        combined = fw.hybrid_v2_decision(case, c_out, ctx["chunks"])
        row["C"] = {"measured": True, "gemini_status": "OK", "gemini_decision": c_out["decision"],
                    "gemini_summary": c_out.get("summary"), "gemini_risk": c_out.get("risk_level"),
                    "missing_requirements": c_out.get("missing_requirements"),
                    "concerns": _concern_rows(c_out, ctx), "gemini_future_date_claims": _future_claims(c_out),
                    "latency_s": round(c_out["generation_latency_ms"] / 1000, 3), **combined}
    elif c_fail is not None:                                 # the request failed: scored fail-closed
        failed = _combine(ctx, {"status": "FAILED", "failure_category": c_fail})
        row["C"] = {"measured": True, "gemini_status": "FAILED", "failure_category": c_fail,
                    "decision": failed.decision, "workflow_state": failed.workflow_state, "triggers": failed.triggers}
    else:                                                    # never requested (run stopped): excluded from metrics
        row["C"] = {"measured": False, "gemini_status": "NOT_RUN", "decision": None, "workflow_state": None}
    # B - existing V3 + Gemini (production prompt), only where it was run
    if b_out is not None:
        existing = fw.hybrid_decision(case, b_out)
        row["B"] = {"measured": True, "gemini_status": "OK", "gemini_decision": b_out["decision"],
                    "gemini_summary": b_out.get("summary"), "red_flag_texts": b_out.get("red_flag_texts"),
                    "missing_requirements": b_out.get("missing_requirements"),
                    "gemini_future_date_claims": _future_claims(b_out),
                    "latency_s": round(b_out["generation_latency_ms"] / 1000, 3),
                    "decision": existing["decision"], "workflow_state": existing["workflow_state"],
                    "escalated_by_gemini": existing["escalated_by_gemini"]}
    elif b_attempted:
        existing = fw.hybrid_decision(case, None)
        row["B"] = {"measured": True, "gemini_status": "FAILED", "failure_category": b_fail,
                    "decision": existing["decision"], "workflow_state": existing["workflow_state"]}
    else:
        row["B"] = {"measured": False, "decision": None}
    # B' - ablation: existing escalation rule on the date-aware prompt's output (not system B)
    if c_out is not None:
        ablation = fw.hybrid_decision(case, c_out)
        row["B_prime"] = {"decision": ablation["decision"], "workflow_state": ablation["workflow_state"]}
    else:
        row["B_prime"] = {"decision": None}
    row["injections"] = injections(case, ctx)
    row["confirmation"] = confirmation_simulation(ctx)
    return row


def _wilson(k: int, n: int) -> Optional[list]:
    if not n:
        return None
    z, p = 1.96, k / n
    centre, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def system_metrics(rows: List[dict], key: str) -> dict:
    scored = [r for r in rows if r[key].get("decision")]
    fraud = [r for r in scored if r["label"] == "fraudulent"]
    legit = [r for r in scored if r["label"] == "legitimate"]
    d = lambda r: r[key]["decision"]  # noqa: E731
    tp = sum(d(r) in DETECT for r in fraud)
    fp = sum(d(r) in DETECT for r in legit)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / len(fraud) if fraud else None
    return {"cases_scored": len(scored), "fraud_cases": len(fraud), "legit_cases": len(legit),
            "fraud_detected": tp, "recall": recall, "recall_wilson95": _wilson(tp, len(fraud)),
            "false_positive_escalations": fp, "false_positive_rate": fp / len(legit) if legit else None,
            "fpr_wilson95": _wilson(fp, len(legit)), "precision": precision,
            "f1": (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if tp == 0 and scored else None),
            "unsafe_approvals": [r["case_id"] for r in fraud if d(r) == "APPROVED"],
            "unresolved_information_approvals": [r["case_id"] for r in scored if d(r) == "APPROVED"
                                                 and r["scenario_type"] in ("EXPIRED_DOCUMENT", "LEGITIMATE_INCOMPLETE_INFORMATION")],
            "manual_reviews": sum(d(r) in DETECT for r in scored),
            "information_requests": sum(d(r) == "NEEDS_MORE_INFORMATION" for r in scored),
            "verification_errors": sum(d(r) == "VERIFICATION_ERROR" for r in scored),
            "approved_pending_confirmation": sum(d(r) == "APPROVED" for r in scored),
            "decisions": {r["case_id"]: d(r) for r in scored}}


def api_metrics(attempts: List[dict], system: str) -> dict:
    rows = [a for a in attempts if a["system"] == system and a["http_requests"]]
    ok = [a for a in rows if a["status"] == "OK"]
    lat = sorted(a["http_seconds"] for a in ok)          # time inside the HTTP request only (no pacing)
    return {"requests": sum(a["http_requests"] for a in rows), "succeeded": len(ok),
            "failed": len(rows) - len(ok), "failure_categories": dict(Counter(a["category"] for a in rows if a["category"])),
            "success_rate": len(ok) / len(rows) if rows else None,
            "latency_s": {"n": len(lat), "mean": round(statistics.mean(lat), 2) if lat else None,
                          "median": round(statistics.median(lat), 2) if lat else None,
                          "p95_nearest_rank": lat[max(0, math.ceil(0.95 * len(lat)) - 1)] if lat else None,
                          "max": lat[-1] if lat else None}}


def safety_checks(rows: List[dict]) -> dict:
    res = {}

    def verdict(failures, applicable=True):
        return {"result": "N/A" if not applicable else ("PASS" if not failures else "FAIL"), "failures": failures}
    c = lambda r: r["C"]  # noqa: E731
    res["S1_fraud_never_auto_approved"] = verdict(
        [r["case_id"] for r in rows if r["label"] == "fraudulent" and c(r)["decision"] == "APPROVED"])
    res["S1_fraud_never_auto_approved"]["other_systems_approving_fraud"] = [
        f"{r['case_id']}:{s}" for r in rows if r["label"] == "fraudulent" for s in ("A", "B", "B_prime")
        if r[s].get("decision") == "APPROVED"]
    s2 = [r["case_id"] for r in rows if "S2" in r["scenario_checks"] and c(r)["decision"] == "APPROVED"]
    s2 += [f"{r['case_id']}:approved-with-open-items" for r in rows if c(r)["decision"] == "APPROVED"
           and (c(r).get("information_requests") or c(r).get("unverified_concerns"))]
    s2 += [f"{r['case_id']}:{n}" for r in rows for n, x in r["injections"]["model_outputs"].items()
           if x["decision"] == "APPROVED" and r["scenario_checks"] and "S2" in r["scenario_checks"]]
    res["S2_missing_information_never_approved"] = verdict(s2)
    s3 = [f"{r['case_id']}:measured" for r in rows if c(r)["decision"] in DETECT
          and c(r).get("triggers", [""])[0] not in INDEPENDENT_BASIS | {"GEMINI_EXPLICIT_FRAUD_WARNING", "GROUNDED_CONTRADICTION"}]
    s3 += [f"{r['case_id']}:{n}" for r in rows for n in ("UNGROUNDED_WARNING_WITH_INFO_REQUEST",
                                                          "UNGROUNDED_WARNING_WITH_APPROVAL", "UNGROUNDED_FREE_TEXT_WARNING")
           if r["injections"]["model_outputs"][n]["decision"] in DETECT
           and r["injections"]["model_outputs"][n]["trigger"] not in INDEPENDENT_BASIS]
    res["S3_unsupported_warnings_do_not_escalate"] = verdict(s3)
    strict = [f"{r['case_id']}:measured" for r in rows if c(r).get("triggers", [""])[0] == "GEMINI_EXPLICIT_FRAUD_WARNING"
              and not any(x["escalates"] for x in c(r).get("concerns", []))]
    strict += [f"{r['case_id']}:{n}" for r in rows for n in ("GEMINI_FLAGS_UNGROUNDED", "GEMINI_REJECTS_UNGROUNDED")
               if r["injections"]["model_outputs"][n]["trigger"] == "GEMINI_EXPLICIT_FRAUD_WARNING"]
    res["S3_strict_no_ungrounded_explicit_recommendation_escalates"] = verdict(strict)
    s4_rows = [r for r in rows if "S4" in r["scenario_checks"] and c(r)["decision"] is not None]
    res["S4_genuine_contradictions_reviewed"] = verdict(
        [r["case_id"] for r in s4_rows if c(r)["decision"] != "FLAG_FOR_REVIEW"], applicable=bool(s4_rows))
    res["S4_genuine_contradictions_reviewed"]["basis"] = {r["case_id"]: (c(r).get("triggers") or [None])[0]
                                                          for r in s4_rows}
    s5 = []
    for r in rows:
        has_future = bool(r["future_dated_documents"])
        for concern in c(r).get("concerns", []):
            if concern["type"] == "DATE_CLAIM" and claims_future_date(concern["text"]) and concern["vetoed"] == has_future:
                s5.append(f"{r['case_id']}:measured:{concern['text'][:60]}")
        for n in ("FUTURE_DATE_CLAIM_WITH_INFO_REQUEST", "FUTURE_DATE_CLAIM_WITH_APPROVAL"):
            x = r["injections"]["model_outputs"][n]
            if has_future and x["decision"] not in DETECT:
                s5.append(f"{r['case_id']}:{n}:future document not sent to review")
            if not has_future and (not x["vetoed"] or x["decision"] in DETECT and x["trigger"] not in INDEPENDENT_BASIS):
                s5.append(f"{r['case_id']}:{n}:unsupported future claim not vetoed")
    res["S5_future_date_claims_checked_against_dates"] = verdict(s5)
    s6 = []
    for r in rows:
        v3 = r["A"]["decision"]
        if c(r)["decision"] == "REJECTED" and v3 != "REJECTED":
            s6.append(f"{r['case_id']}:measured-rejected")
        if c(r)["decision"] == "APPROVED" and v3 != "APPROVED":
            s6.append(f"{r['case_id']}:measured-approved-without-V3")
        a = r["injections"]["model_outputs"]["GEMINI_APPROVES_CLEAN"]
        if a["decision"] == "APPROVED" and (v3 != "APPROVED" or a["state"] != "ELIGIBLE_PENDING_CONFIRMATION"):
            s6.append(f"{r['case_id']}:injected-approval")
        if r["injections"]["model_outputs"]["GEMINI_REJECTS_UNGROUNDED"]["decision"] == "REJECTED" and v3 != "REJECTED":
            s6.append(f"{r['case_id']}:injected-rejection")
    res["S6_gemini_cannot_authorise_or_reject_alone"] = verdict(s6)
    s7 = [f"{r['case_id']}:{s}" for r in rows for s in ("A", "B", "B_prime", "C")
          if (r[s].get("workflow_state") or r[s].get("state")) == "VERIFIED_ACTIVE"]
    s7 += [f"{r['case_id']}:injection:{n}" for r in rows for group in r["injections"].values()
           for n, x in group.items() if x["state"] == "VERIFIED_ACTIVE"]
    s7 += [f"{r['case_id']}:confirmation" for r in rows if not r["confirmation"]["mandatory"]]
    res["S7_external_confirmation_mandatory"] = verdict(s7)
    s8 = [f"{r['case_id']}:{n}" for r in rows for n, x in r["injections"]["api_failures"].items()
          if x["decision"] == "APPROVED" or x["state"] in ("ELIGIBLE_PENDING_CONFIRMATION", "VERIFIED_ACTIVE")
          or (x["trigger"] not in INDEPENDENT_BASIS and x["decision"] != "VERIFICATION_ERROR")]
    s8 += [f"{r['case_id']}:measured" for r in rows if c(r)["gemini_status"] == "FAILED" and c(r)["decision"] == "APPROVED"]
    s8 += [f"{r['case_id']}:measured-B" for r in rows if r["B"].get("gemini_status") == "FAILED" and r["B"]["decision"] == "APPROVED"]
    res["S8_api_failures_fail_closed"] = verdict(s8)
    return res


def analyze(run_dir: Path) -> dict:
    cases = load_run_cases(run_dir)
    log = RunLog(run_dir)
    attempts = log.attempts()
    outputs = {(o["system"], o["case_id"]): o["record"] for o in log.outputs()}
    rows = []
    for case in cases:
        cid = case["case_id"]
        c_hist, b_hist = log.history("C", cid, requests_only=True), log.history("B", cid, requests_only=True)
        rows.append(analyze_case(case, outputs.get(("C", cid)), None if not c_hist or c_hist[-1] == "OK" else c_hist[-1],
                                 outputs.get(("B", cid)), None if not b_hist or b_hist[-1] == "OK" else b_hist[-1],
                                 bool(b_hist)))
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    audit = AuditedPost(None, run_dir / "http_requests.jsonl")
    http = [json.loads(l) for l in (run_dir / "http_requests.jsonl").read_text().splitlines() if l.strip()] \
        if (run_dir / "http_requests.jsonl").exists() else []
    result = {
        "classification": "DEVELOPMENT evidence only: 8 developer-authored synthetic scenarios, author-intended labels.",
        "mode": manifest["mode"], "reference_date_asia_kolkata": manifest["reference_date_asia_kolkata"],
        "model": manifest["model"],
        "api_usage": {"http_requests": audit.count(), "approved_limit": APPROVED_CALL_LIMIT,
                      "within_limit": audit.count() <= APPROVED_CALL_LIMIT,
                      "by_stage": dict(Counter(h["stage"] for h in http)),
                      "by_model": dict(Counter(h["model"] for h in http)),
                      "stopped_reason": next((a["stop"] for a in reversed(attempts) if a.get("stop")), None)},
        "metrics_measured_on_new_cases": {
            "A_frozen_v3": system_metrics(rows, "A"),
            "B_existing_v3_gemini": system_metrics(rows, "B"),
            "C_improved_v3_gemini": system_metrics(rows, "C"),
            "B_prime_ablation_existing_rule_on_C_output": system_metrics(rows, "B_prime")},
        "api_reliability": {"C_date_aware_prompt": api_metrics(attempts, "C"),
                            "B_production_prompt": api_metrics(attempts, "B")},
        "safety_checks": safety_checks(rows),
        "rows": rows,
    }
    return result


def write_outputs(run_dir: Path, result: dict) -> None:
    (run_dir / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
                                          encoding="utf-8")
    with (run_dir / "per_case.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "scenario_type", "label", "A_v3", "B_existing", "B_prime_ablation", "C_gemini",
                         "C_final", "C_state", "C_trigger", "C_latency_s", "future_dated_docs", "expired_docs"])
        for r in result["rows"]:
            writer.writerow([r["case_id"], r["scenario_type"], r["label"], r["A"]["decision"], r["B"].get("decision") or "",
                             r["B_prime"].get("decision") or "", r["C"].get("gemini_decision") or r["C"].get("failure_category"),
                             r["C"]["decision"], r["C"]["workflow_state"], (r["C"].get("triggers") or [""])[0],
                             r["C"].get("latency_s", ""), ";".join(r["future_dated_documents"]), ";".join(r["expired_documents"])])


# ------------------------------------------------------------------ CLI
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "register", "dry-run", "execute", "analyze"])
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--pacing-seconds", type=float, default=6.0)
    args = parser.parse_args(argv)
    ref = reference_date()

    if args.command == "check":
        cases = render_cases(ref)
        result = {"reference_date_asia_kolkata": ref.isoformat(), "utc_date": datetime.now(timezone.utc).date().isoformat(),
                  "preflight": preflight(cases), "call_plan": call_plan(), "preregistration": preregistration_status()}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    if args.command == "register":
        if PREREG_MANIFEST.exists():
            raise SystemExit("prereg_manifest.json exists; a registered protocol is never re-registered in place")
        check = preflight(render_cases(ref))
        if not check["ok"]:
            raise SystemExit("Pre-flight failed: " + "; ".join(check["problems"]))
        manifest = {"registered_at_utc": datetime.now(timezone.utc).isoformat(),
                    "files": {p: _sha(ROOT / p) for p in REGISTERED_FILES},
                    "rule": "Commit this manifest before any API call. The scenarios, labels, metrics and safety "
                            "criteria in these files are not changed after results are seen."}
        PREREG_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        return manifest
    if args.command == "analyze":
        run_dir = args.output_dir or LIVE_DIR
        result = analyze(run_dir)
        write_outputs(run_dir, result)
        print(json.dumps({k: result[k] for k in ("api_usage", "metrics_measured_on_new_cases", "safety_checks")},
                         indent=2, default=str))
        return result
    if args.command == "dry-run":
        if not args.output_dir:
            raise SystemExit("dry-run needs --output-dir (outside evaluation/runs)")
        cases = start_run(args.output_dir, ref, "dry-run")
        transport, audit = make_transport(FakeGemini(), "dry-run-key", args.output_dir, 0.0)
        state = asyncio.run(run_jobs(cases, transport, audit, RunLog(args.output_dir)))
        result = analyze(args.output_dir)
        write_outputs(args.output_dir, result)
        print(json.dumps({"state": state, "api_usage": result["api_usage"]}, indent=2))
        return result

    # execute - every guard runs before any request
    if os.environ.get(fw.APPROVAL_ENV) != "1":
        raise SystemExit(f"Refusing to call Gemini: set {fw.APPROVAL_ENV}=1 to record explicit approval")
    if os.environ.get("GEMINI_MODEL") != MODEL or settings.GEMINI_MODEL != MODEL:
        raise SystemExit(f"Refusing: this experiment uses {MODEL}; set GEMINI_MODEL={MODEL} for this process only")
    if not args.max_calls or args.max_calls > APPROVED_CALL_LIMIT:
        raise SystemExit(f"Refusing: --max-calls must be given and at most {APPROVED_CALL_LIMIT}")
    if not settings.GEMINI_API_KEY:
        raise SystemExit("Refusing: GEMINI_API_KEY is not configured")
    prereg = preregistration_status()
    if not (prereg["matches"] and prereg["committed"]):
        raise SystemExit(f"Refusing: the pre-registration is missing, changed or uncommitted: {prereg}")
    prod = production_unchanged()
    if not prod["hybrid_v2_freeze_valid"] or not prod["production_default_model_is_3_8"] or prod["uncommitted_changes_under_app"]:
        raise SystemExit(f"Refusing: production / freeze check failed: {prod}")
    run_dir = LIVE_DIR
    if args.resume:
        if not run_dir.exists():
            raise SystemExit("Nothing to resume")
        stop = RunLog(run_dir).final_stop()
        if stop:
            raise SystemExit(f"Refusing to resume: the run stopped for good ({stop})")
        cases = load_run_cases(run_dir)
    else:
        if run_dir.exists():
            raise SystemExit(f"{run_dir} exists: the live evaluation runs once (use --resume after a quota stop)")
        check = preflight(render_cases(ref))
        if not check["ok"]:
            raise SystemExit("Pre-flight failed: " + "; ".join(check["problems"]))
        cases = start_run(run_dir, ref, "live")
    from app.services.gemini_api import post_json
    transport, audit = make_transport(post_json, settings.GEMINI_API_KEY, run_dir, args.pacing_seconds)
    transport.max_calls = min(args.max_calls, APPROVED_CALL_LIMIT)
    state = asyncio.run(run_jobs(cases, transport, audit, RunLog(run_dir)))
    result = analyze(run_dir)
    write_outputs(run_dir, result)
    print(json.dumps({"state": state, "api_usage": result["api_usage"]}, indent=2))
    return result


if __name__ == "__main__":
    main()
