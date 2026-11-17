"""Evaluation runner for the v5 independent test (offline by default; live only with written authorisation).

Commands (see evaluation/run_independent_test_v5.py):
  plan       offline: request cap, elapsed time, token and cost estimates, design alternatives.  No network.
  dry-run    engineering fixtures or a pilot file only, with the scripted fake Gemini.  No network.
  execute    live.  Refuses unless the kit is sealed, every freeze verifies, the submission and labels are sealed,
             a written authorisation file matches the plan, SEVAFUND_GEMINI_EVAL_APPROVED=1 and a key is configured.
  status     counters only (requests, failure categories, cases completed, pause/stop reason) - never decisions.

The runner never parses labels: for a live main run it only checks that the label file's SHA-256 matches its seal.
Outputs contain case IDs, scenario groups and system outputs - no labels and no author-intent fields.
"""
import asyncio
import json
import math
import os
import platform
import random
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import config, pipeline, retrieval, stats
from .transport import AuditedTransport, PolicyState, ScriptedGemini, StopPolicy

if str(config.EVALUATION) not in sys.path:
    sys.path.insert(0, str(config.EVALUATION))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ordered(cases: List[dict], seed: int) -> List[dict]:
    """Pre-registered random order (interleaves strata, so outages do not cluster in one stratum)."""
    by_id = {c["case_id"]: c for c in cases}
    ids = sorted(by_id)
    random.Random(seed).shuffle(ids)
    return [by_id[i] for i in ids]


def request_cap(n_cases: int, prereg: dict, pilot: bool = False) -> int:
    budget = prereg["budget"]
    return budget["pilot_requests"] if pilot else n_cases + math.ceil(budget["retry_share"] * n_cases)


def retry_allowance(n_cases: int, prereg: dict, pilot: bool = False) -> int:
    return max(0, request_cap(n_cases, prereg, pilot) - n_cases)


# ------------------------------------------------------------------ integrity
def integrity() -> dict:
    """Freezes, production default and a clean app/ tree.  Read-only."""
    from freeze_hybrid_v2 import verify as verify_v2
    from freeze_hybrid_v3 import verify as verify_v3_candidate
    from verify_candidate_v3_freeze import verify as verify_v3
    candidate, v2, v3 = verify_v3_candidate(), verify_v2(), verify_v3()
    config_text = (config.ROOT / "app/config.py").read_text(encoding="utf-8")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "app/"], capture_output=True, text=True,
                           cwd=config.ROOT).stdout.strip()
    result = {"hybrid_v3_freeze_valid": candidate["valid"], "behavioural_fingerprint": candidate["behavioural_fingerprint"],
              "hybrid_v2_freeze_valid": v2["valid"], "frozen_v3_freeze_valid": v3["valid"],
              "production_default_model_is_3_8": 'os.getenv("GEMINI_MODEL", "gemini-3.8-flash")' in config_text,
              "uncommitted_changes_under_app": bool(dirty)}
    result["ok"] = (result["hybrid_v3_freeze_valid"] and result["hybrid_v2_freeze_valid"] and result["frozen_v3_freeze_valid"]
                    and result["production_default_model_is_3_8"] and not result["uncommitted_changes_under_app"])
    return result


def check_authorisation(path: Optional[Path], prereg: dict, submission: Path, scope: str, plan_cap: int) -> List[str]:
    """The owner's written authorisation for one live stage.  Nothing in this repository creates it."""
    if path is None or not Path(path).exists():
        return ["no written API authorisation file"]
    auth = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = []
    expected = {"scope": scope, "model": prereg["model"]["id"], "max_embedding_requests": 0, "paid_usage": False,
                "submission_sha256": config.sha256_file(submission)}
    for key, value in expected.items():
        if auth.get(key) != value:
            problems.append(f"authorisation {key} must be {value!r}")
    cap = auth.get("max_generation_requests")
    if not isinstance(cap, int) or cap <= 0 or cap > plan_cap:
        problems.append(f"authorisation max_generation_requests must be a positive integer no larger than the plan ({plan_cap})")
    if not auth.get("authorized_by") or not auth.get("authorized_at"):
        problems.append("authorisation needs authorized_by and authorized_at")
    return problems


# ------------------------------------------------------------------ run directory
class RunDir:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.manifest, self.state = self.path / "run_manifest.json", self.path / "state.json"
        self.requests, self.attempts, self.outputs = (self.path / "requests.jsonl", self.path / "attempts.jsonl",
                                                       self.path / "outputs.jsonl")

    @staticmethod
    def _read(path: Path) -> List[dict]:
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def attempt_rows(self) -> List[dict]:
        return self._read(self.attempts)

    def output_rows(self) -> List[dict]:
        return self._read(self.outputs)

    def append(self, path: Path, row: dict) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")

    def load_state(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def save_state(self, state: dict) -> None:
        self.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _config_hash(manifest: dict) -> str:
    keys = ("mode", "submission_sha256", "prereg_sha256", "model", "cap", "retry_allowance", "case_order")
    return config.sha256_text(json.dumps({k: manifest.get(k) for k in keys}, sort_keys=True))


def prepare(run_dir: Path, mode: str, cases: List[dict], submission: Path, prereg: dict, cap: int, allowance: int,
            resume: bool, extra: Optional[dict] = None, clock: Callable[[], datetime] = utcnow) -> RunDir:
    rd = RunDir(run_dir)
    order = [c["case_id"] for c in ordered(cases, prereg["analysis"]["order_seed"])]
    manifest = {"mode": mode, "submission": str(submission), "submission_sha256": config.sha256_file(submission),
                "prereg_sha256": config.sha256_file(config.PREREG_PATH), "model": prereg["model"]["id"],
                "cap": cap, "retry_allowance": allowance, "case_order": order,
                "retrieval": prereg["retrieval"]["mode"], "reference_date_rule": prereg["reference_date"]["rule"],
                "systems": prereg["systems"], "simulation_disclaimer": prereg["analysis"]["simulation_disclaimer"],
                "python": platform.python_version(),
                "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                           cwd=config.ROOT).stdout.strip(), **(extra or {})}
    if rd.path.exists():
        if not resume:
            raise SystemExit(f"{rd.path} exists: a run directory is never reused (use --resume to continue it)")
        recorded = json.loads(rd.manifest.read_text(encoding="utf-8"))
        if _config_hash(recorded) != _config_hash(manifest):
            raise SystemExit("Refusing to resume: the configuration differs from the recorded run")
        return rd
    if resume:
        raise SystemExit(f"{rd.path} does not exist; nothing to resume")
    rd.path.mkdir(parents=True)
    manifest["started_at_utc"] = clock().isoformat()
    rd.manifest.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    rd.save_state({"status": "PREPARED", "policy": PolicyState(started_at=manifest["started_at_utc"]).__dict__})
    return rd


# ------------------------------------------------------------------ the loop
async def run_cases(rd: RunDir, cases: List[dict], prereg: dict, post, api_key: str,
                    clock: Callable[[], datetime] = utcnow, sleep=asyncio.sleep, pacing: Optional[float] = None) -> dict:
    from app.services.development_gemini_verification import verify_with_gemini
    manifest = json.loads(rd.manifest.read_text(encoding="utf-8"))
    by_id = {c["case_id"]: c for c in cases}
    saved = rd.load_state()
    policy = StopPolicy(prereg["stopping_rules"], manifest["cap"], manifest["retry_allowance"],
                        PolicyState(**saved["policy"]), prereg["budget"]["max_retries_per_case"])
    if saved["status"] == "STOPPED" or saved["status"] == "COMPLETE":
        return {"status": saved["status"], "reason": saved.get("reason")}
    transport = AuditedTransport(None, rd.requests, manifest["cap"], prereg["model"]["id"], clock)
    transport.post = post(transport) if callable(post) and getattr(post, "wants_transport", False) else post
    pacing = prereg["budget"]["pacing_seconds"] if pacing is None else pacing
    tolerance = prereg["analysis"]["amount_check_tolerance"]
    done = {o["case_id"] for o in rd.output_rows()}

    def finish(status: str, action=None) -> dict:
        state = {"status": status, "policy": policy.state.__dict__,
                 "reason": action.reason if action else None,
                 "resume_not_before": action.resume_not_before if action else None,
                 "updated_at_utc": clock().isoformat()}
        rd.save_state(state)
        return state

    async def finalise(case: dict, outcome: dict, attempts: int) -> None:
        data = case["input"]
        reference = date.fromisoformat(data["submitted_on"])
        chunks, coverage = await retrieval.retrieve(data)
        systems = pipeline.run_systems(case, outcome, chunks, reference, tolerance)
        rd.append(rd.outputs, {"case_id": case["case_id"], "scenario_group": case["scenario_group"],
                               "category": case["category"], "reference_date": reference.isoformat(),
                               "retrieval": coverage, "gemini": pipeline.gemini_summary(outcome),
                               "gemini_requests": attempts, "systems": systems})

    for case_id in manifest["case_order"]:
        if case_id in done:
            continue
        case = by_id[case_id]
        data = case["input"]
        reference = date.fromisoformat(data["submitted_on"])
        attempts = [a for a in rd.attempt_rows() if a["case_id"] == case_id and a["kind"] != "quota"]
        while True:
            if attempts and attempts[-1]["kind"] == "transient":
                if len(attempts) > policy.max_retries:          # retry already used: the failure is final
                    await finalise(case, {"status": "FAILED", "failure_category": attempts[-1]["category"],
                                          "model": prereg["model"]["id"]}, len(attempts))
                    break
            action = policy.before_request(clock(), transport.sent())
            if action.kind in ("STOP", "PAUSE"):
                return finish("STOPPED" if action.kind == "STOP" else "PAUSED", action)
            if attempts and attempts[-1]["kind"] == "transient":
                claim = policy.claim_retry()
                if claim.kind == "STOP":
                    return finish("STOPPED", claim)
                if claim.kind == "CONTINUE":
                    await finalise(case, {"status": "FAILED", "failure_category": attempts[-1]["category"],
                                          "model": prereg["model"]["id"]}, len(attempts))
                    break
            transport.current_case = case_id
            chunks, _ = await retrieval.retrieve(data)
            outcome = (await verify_with_gemini(data, chunks, reference, submitted_on=reference, transport=transport,
                                                api_key=api_key, model=prereg["model"]["id"], max_attempts=1)).model_dump()
            if not (transport.last or {}).get("sent"):
                reason = "CALL_LIMIT_REACHED" if (transport.last or {}).get("category") == "BUDGET_EXHAUSTED" else \
                    f"NOT_SENT:{(transport.last or {}).get('category') or outcome.get('failure_category')}"
                return finish("STOPPED", policy._stop(reason))
            category = outcome["failure_category"] if outcome["status"] == "FAILED" else None
            kind = policy.classify(category)
            row = {"case_id": case_id, "category": category, "kind": kind, "at": clock().isoformat()}
            rd.append(rd.attempts, row)
            if kind != "quota":
                attempts.append(row)
            history = [a["category"] for a in rd.attempt_rows()]
            action = policy.after_request(clock(), history, len(attempts))
            if kind in ("ok", "invalid_output"):          # an answer was received: always keep it
                await finalise(case, outcome, len(attempts))
                if action.kind == "STOP":
                    return finish("STOPPED", action)
                break
            if action.kind == "STOP":                       # configuration error or transient rate: case stays pending
                return finish("STOPPED", action)
            if action.kind == "PAUSE":                      # quota, or a run of transient failures: case stays pending
                return finish("PAUSED", action)
            if action.kind == "CONTINUE":                   # transient failure on the case's retry: final
                await finalise(case, outcome, len(attempts))
                break
            await sleep(prereg["stopping_rules"]["retry_wait_seconds"] if pacing else 0)
        if pacing:
            await sleep(pacing)
    return finish("COMPLETE")


# ------------------------------------------------------------------ status (counters only)
def status(run_dir: Path) -> dict:
    rd = RunDir(run_dir)
    manifest = json.loads(rd.manifest.read_text(encoding="utf-8"))
    state = rd.load_state()
    requests = RunDir._read(rd.requests)
    from collections import Counter
    return {"status": state["status"], "reason": state.get("reason"), "resume_not_before": state.get("resume_not_before"),
            "requests_sent": len(requests), "cap": manifest["cap"],
            "requests_by_outcome": dict(Counter(r["category"] or "OK" for r in requests)),
            "retries_used": state["policy"]["retries_used"], "retry_allowance": manifest["retry_allowance"],
            "cases_completed": len(rd.output_rows()), "cases_total": len(manifest["case_order"])}


# ------------------------------------------------------------------ engineering dry run
def dry_run(submission: Path, run_dir: Path, script: Dict[str, List[str]], prereg: Optional[dict] = None,
            pilot: bool = False, resume: bool = False, clock: Callable[[], datetime] = utcnow) -> dict:
    """Scripted fake Gemini, engineering fixtures (ENG-) or a pilot file only.  No network."""
    prereg = prereg or config.load_prereg()
    cases = config.read_jsonl(submission)
    prefixes = (prereg["design"]["engineering_case_id_prefix"], prereg["design"]["pilot_case_id_prefix"])
    if not all(str(c["case_id"]).startswith(prefixes) for c in cases):
        raise SystemExit("dry-run accepts only engineering fixtures (ENG-) or pilot cases (P5-); the independent "
                         "test set is never run before the authorised live run")
    cap = request_cap(len(cases), prereg, pilot)
    rd = prepare(run_dir, "engineering-dry-run", cases, submission, prereg, cap, retry_allowance(len(cases), prereg, pilot),
                 resume, {"fake_gemini": True, "api_calls": 0}, clock)
    by_id = {c["case_id"]: c for c in cases}

    def scripted(transport):
        return ScriptedGemini(script, by_id, transport)
    scripted.wants_transport = True
    return asyncio.run(run_cases(rd, cases, prereg, scripted, api_key="engineering-fake-key", clock=clock,
                                 sleep=_no_sleep, pacing=0))


async def _no_sleep(_seconds):
    return None


# ------------------------------------------------------------------ live (refuses without authorisation)
def live_preconditions(submission: Path, submission_seal: Path, prereg: dict, scope: str, authorisation: Optional[Path],
                       label_file: Optional[Path] = None, label_seal: Optional[Path] = None) -> dict:
    from . import kit
    problems = []
    if prereg.get("status") != "APPROVED":
        problems.append("the pre-registration is not APPROVED")
    kit_state = kit.verify()
    if not kit_state["valid"]:
        problems.append(f"the evaluation kit is not sealed or has changed: {kit_state.get('problems')}")
    checks = integrity()
    if not checks["ok"]:
        problems.append(f"integrity checks failed: {checks}")
    cases = config.read_jsonl(submission)
    seal_record = json.loads(Path(submission_seal).read_text(encoding="utf-8")) if Path(submission_seal).exists() else {}
    if seal_record.get("sha256") != config.sha256_file(submission) or seal_record.get("profile") != "full":
        problems.append("the submission is not sealed under the full profile, or differs from its seal")
    if scope == "pilot" and not seal_record.get("pilot"):
        problems.append("a pilot run needs a sealed pilot file")
    if scope == "main":
        if label_file is None or label_seal is None or not Path(label_seal).exists() or \
                json.loads(Path(label_seal).read_text(encoding="utf-8")).get("sha256") != config.sha256_file(label_file):
            problems.append("adjudicated labels are not sealed, or differ from their seal (only the hash is checked)")
    if any(c.get("provenance") != "synthetic" for c in cases):
        problems.append("non-synthetic cases need a separate data-processing approval")
    plan_cap = request_cap(len(cases), prereg, scope == "pilot")
    problems += check_authorisation(authorisation, prereg, submission, scope, plan_cap)
    if os.environ.get(config.APPROVAL_ENV) != "1":
        problems.append(f"{config.APPROVAL_ENV}=1 is not set")
    model_env = os.environ.get("GEMINI_MODEL")
    if model_env and model_env != prereg["model"]["id"]:
        problems.append(f"GEMINI_MODEL is set to another model; no substitution is allowed")
    from app.config import settings
    if not settings.GEMINI_API_KEY:
        problems.append("no API key is configured")
    return {"ok": not problems, "problems": problems, "integrity": checks, "plan_cap": plan_cap}


def execute(submission: Path, submission_seal: Path, run_dir: Path, scope: str, authorisation: Path,
            label_file: Optional[Path] = None, label_seal: Optional[Path] = None, resume: bool = False) -> dict:
    prereg = config.load_prereg()
    pre = live_preconditions(submission, submission_seal, prereg, scope, authorisation, label_file, label_seal)
    if not pre["ok"]:
        raise SystemExit("Refusing to make any API call:\n- " + "\n- ".join(pre["problems"]))
    from app.config import settings
    from app.services.gemini_api import post_json
    cases = config.read_jsonl(submission)
    cap = json.loads(Path(authorisation).read_text(encoding="utf-8"))["max_generation_requests"]
    rd = prepare(run_dir, f"live-{scope}", cases, submission, prereg, cap, retry_allowance(len(cases), prereg, scope == "pilot"),
                 resume, {"authorisation_sha256": config.sha256_file(authorisation), "integrity": pre["integrity"],
                          "label_seal_sha256": config.sha256_file(label_seal) if label_seal else None})
    return asyncio.run(run_cases(rd, cases, prereg, post_json, api_key=settings.GEMINI_API_KEY))


# ------------------------------------------------------------------ plan and estimates (offline)
DESIGNS = {
    "A_full_270_groups_2_cases": ({"L": 90, "I": 45, "F": 90, "B": 45}, 2.0),
    "B_full_270_groups_1_case": ({"L": 90, "I": 45, "F": 90, "B": 45}, 1.0),
    "C_reduced_150_groups_1_case": ({"L": 45, "I": 30, "F": 45, "B": 30}, 1.0),
    "D_minimal_90_groups_1_case": ({"L": 30, "I": 15, "F": 30, "B": 15}, 1.0),
}
EFFORT_ASSUMPTIONS = {"author_minutes_per_case": 30, "author_minutes_per_group_environment": 10,
                      "labeller_minutes_per_case": 8, "labellers": 2, "disagreement_share": 0.2,
                      "adjudicator_minutes_per_disagreement": 10, "coordinator_minutes_per_case": 3}


def _prompt_chars(case: dict) -> int:
    from app.services.development_gemini_verification.prompt import build_prompt
    data = case["input"]
    reference = date.fromisoformat(data["submitted_on"])
    chunks, _ = asyncio.run(retrieval.retrieve(data))
    return len(build_prompt(data, chunks, reference, reference))


def _max_prompt_chars(prereg: dict) -> int:
    from app.services.development_gemini_verification.prompt import build_prompt
    words = prereg["retrieval"]["chunking"]["chunk_words"]
    chunk = " ".join(["documentword"] * words)            # 12-character words: a deliberately high bound
    chunks = [{"title": "Document title of moderate length", "doc_type": "HOSPITAL_ESTIMATE", "page": 1,
               "relevance": 1.0, "text": chunk} for _ in range(prereg["retrieval"]["chunking"]["top_k"])]
    data = {"title": "T" * 120, "category": "MEDICAL", "story": "storyword " * 600, "goal_amount": 999999,
            "beneficiary_name": "N" * 60, "beneficiary_type": "SELF", "city": "C" * 30, "state": "S" * 30,
            "documents": [{}] * 8}
    return len(build_prompt(data, chunks, date(2027, 1, 1), date(2027, 1, 1)))


def plan(submission: Optional[Path] = None, prereg: Optional[dict] = None) -> dict:
    prereg = prereg or config.load_prereg()
    daily = prereg["api_usage"]["observed_free_tier_daily_limit"]
    sample = config.read_jsonl(submission) if submission else config.read_jsonl(config.FIXTURES / "submission.jsonl")
    chars = [_prompt_chars(c) for c in sample]
    mean_chars, max_chars = sum(chars) / len(chars), _max_prompt_chars(prereg)
    max_output = prereg["model"]["generation_config"]["maxOutputTokens"]
    designs = []
    for name, (groups, per_group) in DESIGNS.items():
        row = stats.design_row(name, groups, per_group, daily, prereg["budget"]["retry_share"],
                               prereg["budget"]["pilot_requests"])
        n = row["cases"]
        requests = row["generation_requests_max"]
        row["estimated_input_tokens"] = {"typical": int(requests * mean_chars / 4), "upper_bound": int(requests * max_chars / 4)}
        row["output_tokens_upper_bound_visible"] = requests * max_output
        e = EFFORT_ASSUMPTIONS
        groups_total = row["total_groups"]
        row["human_effort_hours"] = {
            "authoring": round((n * e["author_minutes_per_case"] + groups_total * e["author_minutes_per_group_environment"]) / 60),
            "labelling_total": round(n * e["labeller_minutes_per_case"] * e["labellers"] / 60),
            "adjudication": round(n * e["disagreement_share"] * e["adjudicator_minutes_per_disagreement"] / 60),
            "coordination": round(n * e["coordinator_minutes_per_case"] / 60)}
        row["free_tier_api_cost_usd"] = 0
        designs.append(row)
    return {"api_calls_made": 0,
            "model": prereg["model"]["id"], "tier": prereg["api_usage"]["tier"],
            "paid_usage_allowed": prereg["api_usage"]["paid_usage_allowed"],
            "observed_free_tier_daily_limit": daily,
            "budget_formula": prereg["budget"]["formula"],
            "embedding_requests": 0,
            "prompt_size_basis": {"cases": len(sample), "source": str(submission or "engineering fixtures"),
                                  "mean_prompt_chars": round(mean_chars), "max_prompt_chars_bound": max_chars,
                                  "chars_per_token_assumption": 4},
            "token_caveat": "Token counts are character-based estimates. Output tokens are capped at 2,048 visible "
                            "tokens per request; any model 'thinking' tokens are not capped by this setting and are "
                            "unknown until measured (usageMetadata is logged for every request).",
            "cost_note": "Free tier: no charge, but at most about 20 requests a day were observed for this model, and "
                         "free-tier prompts may be used by the provider to improve its products, so only synthetic "
                         "cases may be sent. Paid usage is not approved; a paid estimate needs the provider's current "
                         "per-token price for this model, applied to the token figures here.",
            "effort_assumptions": EFFORT_ASSUMPTIONS,
            "designs": designs}
