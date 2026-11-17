"""Prepared (NOT executed) paired evaluation of offline and Gemini verification.

Configurations, run on identical case IDs:
  heuristics_only     - production local heuristics, no documents/retrieval            (offline)
  heuristics_lexical  - production local heuristics + lexical RAG retrieval            (offline)
  gemini_no_rag       - production Gemini prompt with campaign text only               (1 generation call)
  gemini_rag          - Gemini embeddings retrieval (top-5) + production Gemini prompt (1 embedding + 1 generation)
  hybrid              - frozen V3 + gemini_rag result (Gemini may only escalate) + approval workflow (no extra call)

Design rules
* Default command is `plan`: builds the job list and call budget; makes no network call.
* `execute` refuses to run unless SEVAFUND_GEMINI_EVAL_APPROVED=1, GEMINI_API_KEY is set and --max-calls is
  given.  It never changes billing; quota exhaustion stops the run cleanly and the next run resumes.
* Successful results are cached (cache.jsonl); API failures are recorded separately (failures.jsonl) with a
  sanitized category - never request content, response text or the key.  The production verifier's silent
  local fallback is bypassed: a Gemini failure stays a failure.
* Retrieval and verification are measured separately.  Metrics are computed on the subset of cases that
  every configuration completed (paired), with coverage reported per configuration.
* Only datasets whose every row is `synthetic: true` may be sent, unless an explicit data-authorization
  reference is given; non-synthetic text is redacted before it leaves the machine.
"""
import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib

from app.config import settings
from app.services import rag
from app.services.ai_verifier import AIVerifierService

# `app.services` re-exports the ai_verifier *instance* under the module's name,
# so the module object (whose post_json the production prompt uses) is fetched explicitly.
ai_verifier_module = importlib.import_module("app.services.ai_verifier")
from app.services.gemini_api import GeminiAPIError

CONFIGS = ["heuristics_only", "heuristics_lexical", "gemini_no_rag", "gemini_rag", "hybrid"]
# Opt-in development configurations for the improved system (hybrid v2): the dated prompt (one generation call,
# sharing gemini_rag's retrieval) and the revised escalation policy (no call).
V2_CONFIGS = ["gemini_rag_dated", "hybrid_v2"]
ALL_CONFIGS = CONFIGS + V2_CONFIGS
API_CONFIGS = {"gemini_no_rag", "gemini_rag", "hybrid", "gemini_rag_dated", "hybrid_v2"}
CALLS_PER_CASE = {"gemini_no_rag": {"generation": 1}, "gemini_rag": {"embedding": 1, "generation": 1}, "hybrid": {},
                  "gemini_rag_dated": {"generation": 1}, "hybrid_v2": {}}
# Any of these stops the run (resume later) instead of hammering the API.
STOP_CATEGORIES = {"QUOTA_EXHAUSTED", "RATE_LIMIT", "RESOURCE_EXHAUSTED", "AUTHENTICATION", "PERMISSION_DENIED",
                   "MODEL_NOT_FOUND", "BUDGET_EXHAUSTED"}
APPROVAL_ENV = "SEVAFUND_GEMINI_EVAL_APPROVED"
DEFAULT_DATASET = Path(__file__).with_name("final_test_scenarios_v3.jsonl")
Transport = Callable[..., Awaitable[Dict[str, Any]]]


class BudgetExhausted(GeminiAPIError):
    def __init__(self):
        super().__init__("framework", "BUDGET_EXHAUSTED")


# Generation failures that count towards the early-stop rule (timeouts and server-side errors).
TRANSIENT_FAILURES = {"READ_TIMEOUT", "CONNECT_TIMEOUT", "WRITE_TIMEOUT", "POOL_TIMEOUT", "TIMEOUT", "SERVER_ERROR",
                      "NETWORK_ERROR"}


class DataAuthorizationError(RuntimeError):
    pass


# ---------------------------------------------------------------- data access
def load_cases(path: Path, data_authorization: Optional[str] = None) -> List[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(row.get("synthetic") is True for row in rows) and not data_authorization:
        raise DataAuthorizationError(
            "Dataset contains rows not marked synthetic. Sending real beneficiary documents to an external "
            "service requires an explicit --data-authorization reference (consent / data-processing approval).")
    return rows


_REDACT = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"), (re.compile(r"\+?\d[\d \-]{8,}\d"), "[NUMBER]"),
           (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), "[IFSC]"), (re.compile(r"\b[\w.-]{2,}@[a-z]{2,}\b"), "[UPI]")]


def redact(case: dict) -> dict:
    """Mask beneficiary name, contact details and account identifiers (used for non-synthetic data)."""
    data = json.loads(json.dumps(case["input"]))
    name = data.get("beneficiary_name") or ""
    parts = sorted({part for part in re.findall(r"[A-Za-z]{3,}", name)}, key=len, reverse=True)

    def clean(text: str) -> str:
        if name:
            text = text.replace(name, "[BENEFICIARY]")
            for part in parts:                      # given name or surname used on its own
                text = re.sub(rf"\b{re.escape(part)}\b", "[BENEFICIARY]", text, flags=re.I)
        for pattern, token in _REDACT:
            text = pattern.sub(token, text)
        return text
    for key in ("title", "story"):
        data[key] = clean(data.get(key, ""))
    if name:
        data["beneficiary_name"] = "[BENEFICIARY]"
    data["documents"] = [dict(d, content=clean(d.get("content", ""))) for d in data.get("documents", [])]
    return dict(case, input=data)


def pilot_cases(cases: List[dict], per_label: int) -> List[dict]:
    """Small balanced pilot: `per_label` cases per ground-truth label, rotating through categories
    and taking each from a different scenario family.  Deterministic."""
    chosen = []
    categories = sorted({c["input"]["category"] for c in cases})
    for label in ("legitimate", "fraudulent", "borderline"):
        pool = sorted((c for c in cases if c["ground_truth"] == label), key=lambda c: c["case_id"])
        used_families = set()
        for i in range(per_label):
            category = categories[(i + ("legitimate", "fraudulent", "borderline").index(label)) % len(categories)]
            pick = next((c for c in pool if c["input"]["category"] == category
                         and c.get("scenario_family") not in used_families and c not in chosen), None)
            pick = pick or next((c for c in pool if c not in chosen), None)
            if pick:
                chosen.append(pick)
                used_families.add(pick.get("scenario_family"))
    return sorted(chosen, key=lambda c: c["case_id"])


def sample_cases(cases: List[dict], per_cluster: Optional[int], seed: int, cluster_key: str) -> List[dict]:
    """Deterministic stratified sample: k cases per (cluster, label).  Same IDs for every configuration."""
    if not per_cluster:
        return cases
    groups = defaultdict(list)
    for case in cases:
        groups[(case.get(cluster_key) or case["case_id"], case["ground_truth"])].append(case)
    rng = random.Random(seed)
    chosen = []
    for key in sorted(groups, key=str):
        members = sorted(groups[key], key=lambda c: c["case_id"])
        chosen.extend(rng.sample(members, min(per_cluster, len(members))))
    return sorted(chosen, key=lambda c: c["case_id"])


# ----------------------------------------------------------------------- plan
def build_plan(cases: List[dict], configs: List[str], dataset: Path, per_cluster: Optional[int], seed: int,
               daily_generation_quota: int, daily_embedding_quota: int) -> dict:
    calls = Counter()
    for config in configs:
        for stage, count in CALLS_PER_CASE.get(config, {}).items():
            calls[stage] += count * len(cases)
    if "gemini_rag_dated" in configs and "gemini_rag" not in configs:
        calls["embedding"] += len(cases)                 # retrieval is shared; it is fetched once per case
    separate = max(math.ceil(calls["generation"] / daily_generation_quota) if daily_generation_quota else 0,
                   math.ceil(calls["embedding"] / daily_embedding_quota) if daily_embedding_quota else 0)
    shared = math.ceil(sum(calls.values()) / daily_generation_quota) if daily_generation_quota else 0
    return {
        "dataset": str(dataset), "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "configs": configs, "case_ids": [c["case_id"] for c in cases], "cases": len(cases),
        "sample_per_cluster": per_cluster, "seed": seed,
        "labels": dict(Counter(c["ground_truth"] for c in cases)),
        "api_calls_required": dict(calls), "api_calls_total": sum(calls.values()),
        "assumed_daily_quota": {"generation": daily_generation_quota, "embedding": daily_embedding_quota},
        "estimated_days_at_quota": {
            "if_embedding_quota_is_separate_per_model": separate,
            "if_all_calls_share_the_generation_quota": shared,
            "excludes": "failed requests (each consumes quota and is retried on a later run) and any other use "
                        "of the same API key; check the project's per-model limits in Google AI Studio",
        },
        "http_requests_per_counted_call": 1,
        "model": settings.GEMINI_MODEL, "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "billing": "No billing change is made by this framework. Quotas are an operator-supplied assumption.",
    }


# ---------------------------------------------------------------------- store
class Store:
    """Append-only cache of successes, failures and run state - resumable across quota resets."""

    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.cache_path, self.fail_path, self.state_path = (directory / "cache.jsonl", directory / "failures.jsonl",
                                                            directory / "state.json")
        self.cache: Dict[str, dict] = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.cache[record["key"]] = record

    @staticmethod
    def key(config: str, case_id: str, stage: str, fingerprint: str) -> str:
        return hashlib.sha256(f"{config}|{case_id}|{stage}|{fingerprint}".encode()).hexdigest()[:24]

    def get(self, key: str) -> Optional[dict]:
        return self.cache.get(key)

    def put(self, key: str, record: dict) -> None:
        record = {**record, "key": key, "cached_at": datetime.now(timezone.utc).isoformat()}
        self.cache[key] = record
        with self.cache_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

    def fail(self, record: dict) -> None:
        with self.fail_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**record, "at": datetime.now(timezone.utc).isoformat()}) + "\n")

    def failures(self) -> List[dict]:
        if not self.fail_path.exists():
            return []
        return [json.loads(line) for line in self.fail_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def save_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def cumulative_calls(self) -> Counter:
        """HTTP requests already made by earlier runs of this experiment (budgets are per experiment)."""
        if not self.state_path.exists():
            return Counter()
        return Counter(json.loads(self.state_path.read_text()).get("cumulative_calls", {}))

    def transient_generation_failures(self) -> int:
        return sum(f["stage"] == "generation" and f["category"] in TRANSIENT_FAILURES for f in self.failures())


class BudgetedTransport:
    """Wraps the real (or a fake) POST function: enforces --max-calls, paces requests and counts them.

    Retries inside the shared client are disabled (max_attempts=1), so every counted call is exactly one
    HTTP request against the quota; a failed request is recorded and retried on a later (resumed) run."""

    def __init__(self, post: Transport, api_key: str, max_calls: int, min_interval_seconds: float = 0.0,
                 stage_limits: Optional[Dict[str, int]] = None, already_used: Optional[Counter] = None):
        self.post, self.api_key, self.max_calls = post, api_key, max_calls
        self.min_interval, self._last = min_interval_seconds, 0.0
        self.stage_limits = stage_limits or {}
        self.already_used = Counter(already_used or {})        # calls made by earlier runs of the experiment
        self.calls = Counter()

    async def __call__(self, url, api_key, payload, stage, timeout_seconds, max_attempts=1):
        used = self.already_used + self.calls
        if sum(used.values()) >= self.max_calls or used[stage] >= self.stage_limits.get(stage, self.max_calls):
            raise BudgetExhausted()
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            await asyncio.sleep(wait)
        self.calls[stage] += 1
        self._last = time.monotonic()
        return await self.post(url, self.api_key, payload, stage, timeout_seconds, max_attempts=1)


@contextmanager
def production_prompt_with(transport: BudgetedTransport):
    """Route the production Gemini prompt through the budgeted transport (restored afterwards)."""
    original = ai_verifier_module.post_json
    ai_verifier_module.post_json = transport
    try:
        yield
    finally:
        ai_verifier_module.post_json = original


# ------------------------------------------------------------ configurations
def _documents_as_chunks(case: dict) -> List[dict]:
    chunks = []
    for index, document in enumerate(case["input"].get("documents", [])):
        chunks.extend(rag.chunk_document(document.get("content", ""), {
            "title": document.get("title"), "doc_type": document.get("doc_type"), "file_url": f"doc-{index}"}))
    return chunks


def _query(case: dict) -> str:
    data = case["input"]
    return " ".join([data["title"], data["category"], data.get("beneficiary_name") or "", data["story"]])


def lexical_retrieve(case: dict, top_k: int = 5) -> List[dict]:
    chunks = _documents_as_chunks(case)
    for chunk in chunks:
        chunk["relevance"] = round(rag._lexical_score(_query(case), chunk["text"]), 4)
    return [c for c in sorted(chunks, key=lambda c: c["relevance"], reverse=True) if c["relevance"] > 0][:top_k]


async def embedding_retrieve(case: dict, transport: BudgetedTransport, top_k: int = 5) -> List[dict]:
    """One batchEmbedContents call (query + chunks), same request format as app.services.rag."""
    chunks = _documents_as_chunks(case)
    if not chunks:
        return []
    model = settings.GEMINI_EMBEDDING_MODEL
    requests = [{"model": f"models/{model}", "content": {"parts": [{"text": _query(case)[:8000]}]},
                 "taskType": "RETRIEVAL_QUERY"}]
    requests += [{"model": f"models/{model}", "content": {"parts": [{"text": c["text"][:8000]}]},
                  "taskType": "RETRIEVAL_DOCUMENT"} for c in chunks]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
    data = await transport(url, transport.api_key, {"requests": requests}, "embedding", 20)
    vectors = data.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(requests):
        raise GeminiAPIError("embedding", "INVALID_EMBEDDING_RESPONSE", 200)
    query = vectors[0]["values"]
    for chunk, vector in zip(chunks, vectors[1:]):
        chunk["relevance"] = round(rag._cosine(query, vector["values"]), 4)
    return sorted(chunks, key=lambda c: c["relevance"], reverse=True)[:top_k]


def retrieval_metrics(case: dict, chunks: List[dict]) -> dict:
    """Document coverage always; recall@k / MRR when the dataset provides gold evidence titles."""
    titles = [d.get("title") for d in case["input"].get("documents", [])]
    retrieved_titles = [c["title"] for c in chunks]
    metrics = {"documents": len(titles), "chunks_retrieved": len(chunks),
               "document_coverage": round(len(set(retrieved_titles) & set(titles)) / len(set(titles)), 4) if titles else None,
               "empty_retrieval": bool(titles) and not chunks}
    gold = case.get("gold_evidence_titles")
    if gold:
        hits = [i for i, title in enumerate(retrieved_titles) if title in gold]
        metrics["gold_recall_at_k"] = round(len(set(retrieved_titles) & set(gold)) / len(set(gold)), 4)
        metrics["gold_mrr"] = round(1 / (hits[0] + 1), 4) if hits else 0.0
    return metrics


def _evidence(chunks: List[dict]) -> List[dict]:
    return [{"document_title": c["title"], "doc_type": c["doc_type"], "file_url": None, "page": c.get("page"),
             "excerpt": c["text"], "relevance": c["relevance"]} for c in chunks]


def _legacy_decision(result) -> str:
    return {"AUTO_APPROVE": "APPROVED", "NEEDS_MORE_INFO": "NEEDS_MORE_INFORMATION", "REJECT": "REJECTED"}.get(
        result.recommendation, result.recommendation)


async def run_offline(config: str, case: dict) -> dict:
    """heuristics_only / heuristics_lexical through the production local engine (no key -> no network)."""
    data = case["input"]
    service = AIVerifierService()
    service.api_key = ""
    chunks = [] if config == "heuristics_only" else lexical_retrieve(case)
    started = time.perf_counter()
    result = service._verify_with_local_heuristics(
        title=data["title"], category=data["category"], story=data["story"], goal_amount=data["goal_amount"],
        beneficiary_name=data.get("beneficiary_name"), beneficiary_type=data.get("beneficiary_type", "SELF"),
        location=f"{data.get('city', '')}, {data.get('state', '')}".strip(", "), proof_documents=[],
        supporting_document_count=len({c["title"] for c in chunks}))
    decision = _legacy_decision(result)
    return {"decision": decision, "flagged": decision in ("FLAG_FOR_REVIEW", "REJECTED") or bool(result.red_flags),
            "latency_ms": (time.perf_counter() - started) * 1000,
            "retrieval": retrieval_metrics(case, chunks) if config == "heuristics_lexical" else None}


async def run_gemini(case: dict, chunks: Optional[List[dict]], transport: BudgetedTransport) -> dict:
    data = case["input"]
    service = AIVerifierService()
    service.api_key = transport.api_key
    started = time.perf_counter()
    with production_prompt_with(transport):
        result = await service._verify_with_gemini(
            title=data["title"], category=data["category"], story=data["story"], goal_amount=data["goal_amount"],
            beneficiary_name=data.get("beneficiary_name"), beneficiary_type=data.get("beneficiary_type", "SELF"),
            location=f"{data.get('city', '')}, {data.get('state', '')}".strip(", "),
            proof_documents=[], supporting_evidence=_evidence(chunks or []))
    if result is None:
        raise GeminiAPIError("generation", "NO_VERIFICATION_RESULT", 200)
    decision = _legacy_decision(result)
    return {"decision": decision, "flagged": decision in ("FLAG_FOR_REVIEW", "REJECTED") or bool(result.red_flags),
            "red_flags": len(result.red_flags), "authenticity_score": result.authenticity_score,
            "generation_latency_ms": (time.perf_counter() - started) * 1000, "model": result.model_used,
            "risk_level": result.risk_level, "summary": result.summary, "red_flag_texts": list(result.red_flags),
            "missing_requirements": list(result.missing_requirements),
            "positive_signals": list(result.positive_signals),
            "dimension_scores": result.dimension_scores.model_dump()}


def hybrid_decision(case: dict, gemini_rag: Optional[dict]) -> dict:
    """Frozen V3 decides; Gemini can only escalate; a missing Gemini result blocks approval; workflow applied."""
    from app.services.development_approval_workflow import AutomatedOutcome, start
    from app.services.development_verifier_v3 import verify_case
    from evaluate_development_verifier_v3 import v3_input
    v3_result = verify_case(v3_input(case["input"]))
    v3 = v3_result.decision.value
    if v3 in ("FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR"):
        decision = v3
    elif gemini_rag is None:
        decision = "VERIFICATION_ERROR"
    elif gemini_rag["flagged"]:
        decision = "FLAG_FOR_REVIEW"
    else:
        decision = v3                         # APPROVED or NEEDS_MORE_INFORMATION; Gemini cannot approve
    state = start(AutomatedOutcome(decision=decision, category=case["input"]["category"],
                                   beneficiary_type=case["input"].get("beneficiary_type"))).state.value
    return {"decision": decision, "flagged": decision in ("FLAG_FOR_REVIEW", "REJECTED"), "v3_decision": v3,
            "workflow_state": state, "v3_reasons": v3_result.reasons[:6],
            "v3_finding_codes": sorted({f.code for f in v3_result.findings}),
            "v3_information_requests": v3_result.information_requests[:4],
            "escalated_by_gemini": decision == "FLAG_FOR_REVIEW" and v3 not in ("FLAG_FOR_REVIEW", "REJECTED")}


def reference_date_for(case: dict):
    """The case's submission date if recorded, else today's UTC date (recorded with every result)."""
    from datetime import date as _date
    submitted = case["input"].get("submitted_on")
    return (_date.fromisoformat(submitted) if submitted else datetime.now(timezone.utc).date()), \
        (_date.fromisoformat(submitted) if submitted else None)


async def run_gemini_dated(case: dict, chunks: List[dict], transport: BudgetedTransport) -> dict:
    """Hybrid-v2 Gemini call: dated prompt with categorised, quoted concerns (development path only)."""
    from app.services.development_gemini_verification import verify_with_gemini
    reference, submitted = reference_date_for(case)
    outcome = await verify_with_gemini(case["input"], chunks, reference, submitted, transport=transport,
                                       api_key=transport.api_key, model=settings.GEMINI_MODEL)
    if outcome.status != "OK":
        raise GeminiAPIError("generation", outcome.failure_category or "UNKNOWN")
    return {"decision": outcome.decision, "flagged": outcome.decision in ("FLAG_FOR_REVIEW", "REJECTED")
            or bool(outcome.red_flag_texts), "red_flags": len(outcome.red_flag_texts),
            "red_flag_texts": outcome.red_flag_texts, "missing_requirements": outcome.missing_requirements,
            "concerns": outcome.concerns, "summary": outcome.summary, "risk_level": outcome.risk_level,
            "generation_latency_ms": (outcome.latency_seconds or 0) * 1000, "model": outcome.model,
            "reference_date": reference.isoformat()}


def hybrid_v2_decision(case: dict, dated: dict, chunks: List[dict]) -> dict:
    """Frozen V3 + dated Gemini under the hybrid-v2 policy, then the approval workflow."""
    from app.services.development_gemini_verification import assess_dates, combine
    from app.services.development_verifier_v3 import verify_case
    from evaluate_development_verifier_v3 import v3_input
    from datetime import date as _date
    data = case["input"]
    v3 = verify_case(v3_input(data))
    reference = _date.fromisoformat(dated["reference_date"])
    dates = assess_dates([(d.get("title", ""), d.get("content", "")) for d in data.get("documents", [])], reference)
    campaign_text = " ".join(str(data.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state"))
    out = combine(v3.decision.value, {"status": "OK", **dated}, chunks, campaign_text, dates, category=data["category"],
                  beneficiary_type=data.get("beneficiary_type"), v3_information_requests=v3.information_requests)
    return {"decision": out.decision, "flagged": out.decision in ("FLAG_FOR_REVIEW", "REJECTED"),
            "v3_decision": v3.decision.value, "workflow_state": out.workflow_state, "triggers": out.triggers,
            "reasons": out.reasons, "information_requests": out.information_requests[:6],
            "unverified_concerns": out.unverified_concerns, "vetoed_concerns": out.vetoed_concerns,
            "policy_version": out.policy_version}


# ------------------------------------------------------------------- execute
async def execute(cases: List[dict], configs: List[str], store: Store, transport: Optional[BudgetedTransport],
                  dataset_sha: str, data_authorization: Optional[str] = None,
                  max_transient_generation_failures: Optional[int] = None) -> dict:
    """Run every (config, case) job not already cached.  Stops cleanly on quota/auth/budget errors and, if
    `max_transient_generation_failures` is set, as soon as timeouts/server errors exceed it (all runs counted)."""
    stopped, completed = None, Counter()
    if max_transient_generation_failures is not None and \
            store.transient_generation_failures() > max_transient_generation_failures:
        stopped = "EARLY_STOP_TRANSIENT_FAILURES"
    model = settings.GEMINI_MODEL
    for case in cases:
        outgoing = redact(case) if data_authorization and not case.get("synthetic") else case
        fingerprint = hashlib.sha256(json.dumps(outgoing["input"], sort_keys=True).encode()).hexdigest()[:16]
        for config in configs:
            stage_fp = f"{fingerprint}|{dataset_sha[:12]}|{model if config in API_CONFIGS else 'offline'}"
            key = store.key(config, case["case_id"], "result", stage_fp)
            if store.get(key):
                continue
            if config in API_CONFIGS and transport is None:
                continue                                    # plan / offline-only mode
            if stopped and config in API_CONFIGS:
                continue
            try:
                if config in ("heuristics_only", "heuristics_lexical"):
                    record = await run_offline(config, outgoing)
                elif config == "gemini_no_rag":
                    record = await run_gemini(outgoing, None, transport)
                elif config in ("gemini_rag", "gemini_rag_dated"):
                    retrieval_key = store.key("gemini_rag", case["case_id"], "retrieval", stage_fp)
                    cached = store.get(retrieval_key)
                    if cached:
                        chunks = cached["chunks"]
                    else:
                        started = time.perf_counter()
                        chunks = await embedding_retrieve(outgoing, transport)
                        store.put(retrieval_key, {"config": "gemini_rag", "case_id": case["case_id"],
                                                  "stage": "retrieval", "chunks": chunks,
                                                  "retrieval": retrieval_metrics(outgoing, chunks),
                                                  "latency_ms": (time.perf_counter() - started) * 1000})
                    if config == "gemini_rag":
                        record = await run_gemini(outgoing, chunks, transport)
                    else:
                        record = await run_gemini_dated(outgoing, chunks, transport)
                    record["retrieval"] = retrieval_metrics(outgoing, chunks)
                elif config == "hybrid_v2":                 # reuses the cached dated Gemini result; no call
                    dated = store.get(store.key("gemini_rag_dated", case["case_id"], "result", stage_fp))
                    retrieved = store.get(store.key("gemini_rag", case["case_id"], "retrieval", stage_fp))
                    if dated is None:
                        continue
                    record = hybrid_v2_decision(outgoing, dated, (retrieved or {}).get("chunks", []))
                else:                                       # hybrid reuses the cached gemini_rag result
                    rag_key = store.key("gemini_rag", case["case_id"], "result", stage_fp)
                    rag_record = store.get(rag_key)
                    if rag_record is None:
                        continue                            # wait until gemini_rag has completed for this case
                    record = hybrid_decision(outgoing, rag_record)
                store.put(key, {"config": config, "case_id": case["case_id"], "ground_truth": case["ground_truth"],
                                "category": case["input"]["category"], "stage": "result", **record})
                completed[config] += 1
            except GeminiAPIError as exc:
                store.fail({"config": config, "case_id": case["case_id"], "stage": exc.stage,
                            "category": exc.category, "status_code": exc.status_code,
                            "exception_type": exc.exception_type, "duration_seconds": exc.duration_seconds})
                if exc.category in STOP_CATEGORIES:
                    stopped = exc.category
                elif (max_transient_generation_failures is not None and exc.stage == "generation"
                      and store.transient_generation_failures() > max_transient_generation_failures):
                    stopped = "EARLY_STOP_TRANSIENT_FAILURES"
    cumulative = store.cumulative_calls() + (transport.calls if transport else Counter())
    state = {"updated_at": datetime.now(timezone.utc).isoformat(), "completed_this_run": dict(completed),
             "stopped_reason": stopped, "calls_this_run": dict(transport.calls) if transport else {},
             "cumulative_calls": dict(cumulative),
             "transient_generation_failures_total": store.transient_generation_failures(),
             "resume": "Re-run the same command; cached results are skipped." if stopped else None}
    store.save_state(state)
    return state


# -------------------------------------------------------------------- report
def _pct(values):
    return round(statistics.mean(values), 4) if values else None


def report(cases: List[dict], configs: List[str], store: Store) -> dict:
    results = defaultdict(dict)
    retrieval = defaultdict(list)
    for record in store.cache.values():
        if record.get("stage") == "result":
            results[record["config"]][record["case_id"]] = record
        if record.get("retrieval"):
            retrieval[record["config"]].append(record["retrieval"])
    ids = [c["case_id"] for c in cases]
    paired = [i for i in ids if all(i in results[c] for c in configs)]
    label = {c["case_id"]: c["ground_truth"] for c in cases}
    failures = store.failures()
    out = {"cases_planned": len(ids), "paired_complete_cases": len(paired),
           "coverage": {c: round(len(results[c]) / len(ids), 4) if ids else None for c in configs},
           "verification_on_paired_subset": {}, "retrieval": {}, "reliability": {}}
    for config in configs:
        rows = [results[config][i] for i in paired]
        fraud = [r for r in rows if label[r["case_id"]] == "fraudulent"]
        negatives = [r for r in rows if label[r["case_id"]] != "fraudulent"]
        legit = [r for r in rows if label[r["case_id"]] == "legitimate"]
        tp, fp = sum(r["flagged"] for r in fraud), sum(r["flagged"] for r in negatives)
        out["verification_on_paired_subset"][config] = {
            "cases": len(rows), "recall": round(tp / len(fraud), 4) if fraud else None,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "false_positive_rate": round(fp / len(negatives), 4) if negatives else None,
            "fraudulent_auto_approval_rate": round(sum(r["decision"] == "APPROVED" for r in fraud) / len(fraud), 4) if fraud else None,
            "legitimate_auto_approval_rate": round(sum(r["decision"] == "APPROVED" for r in legit) / len(legit), 4) if legit else None,
            "decisions": dict(Counter(r["decision"] for r in rows)),
        }
        cfg_fail = [f for f in failures if f["config"] == config]
        latencies = [r.get("generation_latency_ms") or r.get("latency_ms") for r in results[config].values()
                     if (r.get("generation_latency_ms") or r.get("latency_ms")) is not None]
        attempted = len(results[config]) + len(cfg_fail)
        out["reliability"][config] = {
            "successes": len(results[config]), "failures": len(cfg_fail),
            "success_rate": round(len(results[config]) / attempted, 4) if attempted else None,
            "failure_categories": dict(Counter(f["category"] for f in cfg_fail)),
            "latency_ms": ({"mean": round(statistics.mean(latencies), 1), "p50": round(statistics.median(latencies), 1),
                            "p95": round(sorted(latencies)[max(0, math.ceil(.95 * len(latencies)) - 1)], 1)}
                           if latencies else None),
        }
    for config, items in retrieval.items():
        out["retrieval"][config] = {
            "cases": len(items), "mean_document_coverage": _pct([i["document_coverage"] for i in items
                                                                 if i["document_coverage"] is not None]),
            "empty_retrieval_rate": _pct([float(i["empty_retrieval"]) for i in items]),
            "mean_gold_recall_at_k": _pct([i["gold_recall_at_k"] for i in items if "gold_recall_at_k" in i]),
            "mean_gold_mrr": _pct([i["gold_mrr"] for i in items if "gold_mrr" in i]),
        }
    return out


# ------------------------------------------------------------------------ CLI
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "offline", "execute", "report"], nargs="?", default="plan")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--experiment", default="gemini_eval_v3_final_sample")
    parser.add_argument("--configs", default=",".join(CONFIGS))
    parser.add_argument("--sample-per-cluster", type=int, default=2,
                        help="cases per (scenario family, label); 0 = all cases")
    parser.add_argument("--cluster-key", default="scenario_family")
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--daily-generation-quota", type=int, default=20)
    parser.add_argument("--daily-embedding-quota", type=int, default=1000)
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-generation-calls", type=int, help="per-experiment cap on generation requests")
    parser.add_argument("--max-embedding-calls", type=int, help="per-experiment cap on embedding requests")
    parser.add_argument("--stop-after-transient-failures", type=int,
                        help="stop when generation timeouts/server errors exceed this number (all runs counted)")
    parser.add_argument("--min-interval-seconds", type=float, default=6.0,
                        help="pause between API requests (default 6s, i.e. at most 10 requests per minute)")
    parser.add_argument("--pilot-per-label", type=int,
                        help="small balanced pilot: N cases per label across categories (overrides sampling)")
    parser.add_argument("--data-authorization")
    parser.add_argument("--output-root", type=Path, default=Path(__file__).with_name("runs"))
    args = parser.parse_args(argv)

    configs = [c for c in args.configs.split(",") if c]
    unknown = set(configs) - set(ALL_CONFIGS)
    if unknown:
        raise SystemExit(f"Unknown configurations: {sorted(unknown)}")
    loaded = load_cases(args.dataset, args.data_authorization)
    cases = (pilot_cases(loaded, args.pilot_per_label) if args.pilot_per_label
             else sample_cases(loaded, args.sample_per_cluster or None, args.seed, args.cluster_key))
    directory = args.output_root / args.experiment
    plan = build_plan(cases, configs, args.dataset, args.sample_per_cluster or None, args.seed,
                      args.daily_generation_quota, args.daily_embedding_quota)
    if args.command == "plan":
        print(json.dumps(plan, indent=2))
        return plan
    transport = None
    if args.command == "execute":                    # every guard runs before anything is written
        if os.environ.get(APPROVAL_ENV) != "1":
            raise SystemExit(f"Refusing to call Gemini: set {APPROVAL_ENV}=1 to record explicit approval")
        if not settings.GEMINI_API_KEY:
            raise SystemExit("Refusing to call Gemini: GEMINI_API_KEY is not configured")
        if not args.max_calls:
            raise SystemExit("Refusing to call Gemini without an explicit --max-calls budget")
        from app.services.gemini_api import post_json
        limits = {k: v for k, v in (("generation", args.max_generation_calls), ("embedding", args.max_embedding_calls))
                  if v is not None}
        transport = BudgetedTransport(post_json, settings.GEMINI_API_KEY, args.max_calls, args.min_interval_seconds,
                                      stage_limits=limits)
    store = Store(directory)
    if transport is not None:
        transport.already_used = store.cumulative_calls()
    plan_path = directory / "plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text())["case_ids"] != plan["case_ids"]:
        raise SystemExit("This experiment's saved plan uses different case IDs; use a new --experiment name")
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if args.command == "report":
        result = report(cases, configs, store)
        (directory / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return result
    state = asyncio.run(execute(cases, configs, store, transport, plan["dataset_sha256"], args.data_authorization,
                                args.stop_after_transient_failures))
    print(json.dumps(state, indent=2))
    return state


if __name__ == "__main__":
    main()
