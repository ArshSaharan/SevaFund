"""Freeze (and verify) hybrid v3 as an evaluation candidate.  Offline only: no API call, no network access.

    python evaluation/freeze_hybrid_v3.py freeze    # writes evaluation/hybrid_v3_freeze.json (refuses to overwrite)
    python evaluation/freeze_hybrid_v3.py verify    # exit 1 if anything recorded has changed

The manifest records:
  * git commits: HEAD at freeze, the commits that introduced hybrid v3 and both earlier freezes, and the main branch;
  * SHA-256 of every hybrid v3 source file, its tests and report, and every frozen dependency (V3, hybrid v2,
    approval workflow, evaluation framework, production-path files) - plus the dependency manifests themselves;
  * the Gemini model and prompt configuration hybrid v3 consumes, captured from the frozen hybrid-v2 client through a
    recording transport (no request is sent), including a fingerprint of a rendered prompt for a fixed synthetic case;
  * the evaluation configuration (policy settings and digests, decision-to-workflow mapping, detection definition,
    retrieval and reference-date conventions used in development);
  * a behavioural fingerprint: hybrid v3 decisions on the 750 benchmark cases (clean Gemini approval assumed) and on
    the 8 date-aware cases under scripted Gemini outputs, with a fixed fallback reference date;
  * test results (full suite, hybrid v3 tests, frozen-benchmark reproducibility check, both earlier freezes);
  * known limitations.

`verify` re-hashes every file, re-checks both earlier freezes, re-renders the prompt fingerprint and recomputes the
behavioural fingerprint.  It does not re-run the test suite (run pytest separately).
"""
import asyncio
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timezone
from importlib import metadata
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

MANIFEST = Path(__file__).with_name("hybrid_v3_freeze.json")
IST = ZoneInfo("Asia/Kolkata")
PACKAGE = "app/services/development_hybrid_v3"
SUPPORTING = ["tests/test_hybrid_v3.py", "evaluation/compare_hybrid_v3_offline.py", "docs/hybrid_v3_safety_changes.md",
              "evaluation/runs/hybrid_v3_offline_20261117T091013Z/report.md",
              "evaluation/runs/hybrid_v3_offline_20261117T091013Z/results.json"]
DEPENDENCY_MANIFESTS = ["evaluation/development_candidate_v3_freeze.json", "evaluation/development_candidate_v3_config.json",
                        "evaluation/hybrid_v2_freeze.json"]
PRODUCTION_PATH = ["app/services/ai_verifier.py", "app/services/rag.py", "app/services/gemini_api.py", "app/config.py",
                   "app/schemas/ai.py", "app/services/fraud_detector.py"]
BENCHMARKS = {"final_test_300": "evaluation/final_test_scenarios_v3.jsonl",
              "fundraising_200": "evaluation/fundraising_scenarios.jsonl",
              "independent_test_150": "evaluation/independent_test_150.jsonl",
              "independent_benchmark_100": "evaluation/independent_benchmark_100.jsonl"}
DA_RENDERED = "evaluation/runs/date_aware_dev_eval_live/rendered_cases.jsonl"
FIXED_FALLBACK_REFERENCE = date(2026, 11, 17)      # the offline run's Asia/Kolkata date; pinned so verify is stable
KNOWN_FAILURES = {"tests.test_campaigns::test_campaign_verification_endpoint"}   # pre-existing HTTP 401, unrelated
FINGERPRINT_MODEL = "fingerprint-model"            # placeholder; the model under test is an evaluation parameter
FINGERPRINT_CASE = {
    "title": "Knee surgery for a farm worker", "category": "MEDICAL", "goal_amount": 120000, "goal_currency": "INR",
    "beneficiary_name": "Test Beneficiary", "beneficiary_type": "SELF", "city": "Testpur", "state": "Teststate",
    "story": "Synthetic fixed text used only to fingerprint the frozen prompt template.",
    "documents": [{"title": "Estimate", "doc_type": "HOSPITAL_ESTIMATE", "content": "Synthetic estimate Rs 1,20,000."}]}
FINGERPRINT_CHUNKS = [{"title": "Estimate", "doc_type": "HOSPITAL_ESTIMATE", "page": 1, "relevance": 1.0,
                       "text": "Synthetic estimate Rs 1,20,000."}]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_json(value) -> str:
    return sha_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode())


def git(*args) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


# ------------------------------------------------------------------ files
def recorded_paths() -> dict:
    v2_files = list(json.loads((ROOT / "evaluation/hybrid_v2_freeze.json").read_text())["files"])
    implementation = [str(p.relative_to(ROOT)) for p in sorted((ROOT / PACKAGE).glob("*.py"))]
    return {"implementation": implementation, "supporting": SUPPORTING, "dependency_manifests": DEPENDENCY_MANIFESTS,
            "frozen_dependencies_and_production_path": sorted(v2_files)}


def current_hashes() -> dict:
    return {group: {p: sha_bytes((ROOT / p).read_bytes()) for p in paths} for group, paths in recorded_paths().items()}


# ------------------------------------------------------------------ model and prompt (captured, never sent)
def prompt_configuration() -> dict:
    from app.services.development_gemini_verification import client
    from app.services.development_gemini_verification.prompt import DATED_SCHEMA

    captured = {}

    async def recording_transport(url, key, payload, stage, timeout, max_attempts=1):
        captured.update(url=url, payload=payload, stage=stage, timeout=timeout, max_attempts=max_attempts,
                        key_is_placeholder=(key == "offline-placeholder-not-a-key"))
        return {}                                  # -> EMPTY_CANDIDATES; nothing leaves the process

    outcome = asyncio.run(client.verify_with_gemini(FINGERPRINT_CASE, FINGERPRINT_CHUNKS, date(2026, 1, 15),
                                                    submitted_on=date(2026, 1, 14), transport=recording_transport,
                                                    api_key="offline-placeholder-not-a-key", model=FINGERPRINT_MODEL))
    payload = captured["payload"]
    generation = {k: v for k, v in payload["generationConfig"].items() if k != "responseSchema"}
    prompt_text = payload["contents"][0]["parts"][0]["text"]
    config_text = (ROOT / "app/config.py").read_text()
    default_line = next(l.strip() for l in config_text.splitlines() if "GEMINI_MODEL: str" in l)
    embedding_line = next(l.strip() for l in config_text.splitlines() if "GEMINI_EMBEDDING_MODEL: str" in l)
    timeout = captured["timeout"]
    return {
        "hybrid_v3_calls_models": False,
        "note": "Hybrid v3 makes no model call. It consumes the GeminiOutcome produced by the frozen hybrid-v2 client "
                "(app/services/development_gemini_verification/client.py) with the frozen date-aware prompt (prompt.py). "
                "One Gemini answer per case therefore feeds both hybrid v2 and hybrid v3, so they can be compared "
                "paired at no extra API cost.",
        "prompt_module": "app/services/development_gemini_verification/prompt.py",
        "client_module": "app/services/development_gemini_verification/client.py",
        "endpoint_template": captured["url"].replace(FINGERPRINT_MODEL, "{model}"),
        "generation_config": generation,
        "response_schema_sha256": sha_json(payload["generationConfig"]["responseSchema"]),
        "response_schema_matches_DATED_SCHEMA": payload["generationConfig"]["responseSchema"] == DATED_SCHEMA,
        "timeout_seconds": {"connect": timeout.connect, "read": timeout.read, "write": timeout.write, "pool": timeout.pool},
        "client_default_max_attempts": captured["max_attempts"],
        "fingerprint": {"case_sha256": sha_json(FINGERPRINT_CASE), "chunks_sha256": sha_json(FINGERPRINT_CHUNKS),
                        "reference_date": "2026-01-15", "submitted_on": "2026-01-14",
                        "rendered_prompt_sha256": sha_bytes(prompt_text.encode()), "rendered_prompt_chars": len(prompt_text),
                        "offline_outcome": outcome.failure_category},
        "model": {"set_by_frozen_code": False,
                  "client_rule": "model argument if given, else settings.GEMINI_MODEL",
                  "production_default_line": default_line,
                  "production_embedding_model_line": embedding_line,
                  "development_runs_used": "gemini-3.6-flash (GEMINI_MODEL override for the evaluation process only)",
                  "independent_evaluation_model": "NOT FIXED - requires approval; the run manifest must record it"},
    }


# ------------------------------------------------------------------ behaviour
def _reference(data: dict) -> tuple:
    from app.services.development_verifier_v3.normalize import find_dates
    if data.get("submitted_on"):
        return date.fromisoformat(data["submitted_on"]), "submitted_on"
    found = [value for d in data.get("documents", []) for value, *_ in find_dates(d.get("content", ""))]
    if found:
        return max(found), "latest_document_date"
    return FIXED_FALLBACK_REFERENCE, "fixed_fallback_2026-11-17"


def behavioural_fingerprint() -> dict:
    import compare_hybrid_v3_offline as offline
    import run_date_aware_dev_eval as ev
    from app.services.development_hybrid_v3 import combine, v3_case
    from app.services.development_verifier_v3 import verify_case
    from app.services.development_verifier_v3.config import DEFAULT_CONFIG

    out = {"assumption": "Benchmarks: Gemini approves cleanly (deterministic layers only), no retrieved chunks. "
                         "Date-aware cases: committed rendered cases, frozen lexical top-5 retrieval, scripted outputs.",
           "sets": {}}
    for name, path in BENCHMARKS.items():
        rows, counts, basis = [], Counter(), Counter()
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            data = case["input"]
            reference, why = _reference(data)
            basis[why] += 1
            result = combine(data, verify_case(v3_case(data), DEFAULT_CONFIG), offline.APPROVE, [], reference)
            rows.append([case["case_id"], result.decision, result.triggers, result.financial_evidence["status"],
                         sorted(f["code"] for f in result.cross_document_findings)])
            counts[f"{case['ground_truth']}|{result.decision}"] += 1
        out["sets"][name] = {"cases": len(rows), "reference_date_basis": dict(basis),
                             "decisions_by_label": dict(sorted(counts.items())), "sha256": sha_json(rows)}
    rows, counts = [], Counter()
    for case in ev.load_run_cases(ROOT / DA_RENDERED.rsplit("/", 1)[0]):
        data = case["input"]
        reference = date.fromisoformat(data["submitted_on"])
        chunks = ev.evidence(case)
        v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
        for scenario, gemini in sorted(offline.SCENARIOS.items()):
            result = combine(data, v3, gemini, chunks, reference)
            rows.append([case["case_id"], scenario, result.decision, result.triggers, result.review_basis])
            counts[f"{case['case_id']}|{scenario}|{result.decision}"] += 1
    out["sets"]["date_aware_8_scripted"] = {"cases": len(rows), "decisions": dict(sorted(counts.items())),
                                            "sha256": sha_json(rows)}
    out["sha256"] = sha_json({k: v["sha256"] for k, v in out["sets"].items()})
    return out


# ------------------------------------------------------------------ configuration
def evaluation_configuration() -> dict:
    from app.services.development_approval_workflow.schemas import INDEPENDENT_SOURCES
    from app.services.development_approval_workflow.workflow import AUTOMATED_TO_STATE
    from app.services.development_gemini_verification import config as v2_config
    from app.services.development_hybrid_v3 import GEMINI_DEPENDENT, POLICY_VERSION, SETTINGS
    from app.services.development_hybrid_v3.config import digest
    from app.services.development_hybrid_v3.confirmation import REQUIRED_CHECKS

    v3_manifest = json.loads((ROOT / "evaluation/development_candidate_v3_freeze.json").read_text())
    return {
        "hybrid_v3": {"policy_version": POLICY_VERSION, "settings": SETTINGS, "settings_digest": digest()},
        "hybrid_v2_consumed": {"policy_version": v2_config.POLICY_VERSION, "settings": v2_config.SETTINGS,
                               "settings_digest": v2_config.digest(),
                               "used_for": "build_concerns (grounding Gemini concerns in retrieved evidence)"},
        "frozen_v3": {"config_sha256": v3_manifest.get("config_sha256"),
                      "package_sha256": v3_manifest.get("v3_package", {}).get("combined")},
        "policy_order": ["V3 error", "V3 effective contradiction", "cross-document contradiction",
                         "future-dated document or record", "Gemini failed -> VERIFICATION_ERROR",
                         "Gemini FLAG or REJECT -> FLAG_FOR_REVIEW (never REJECTED)", "grounded Gemini contradiction",
                         "open evidence (incl. financial gate) -> NEEDS_MORE_INFORMATION",
                         "all pass -> APPROVED (= ELIGIBLE_PENDING_CONFIRMATION, authenticity UNCONFIRMED)",
                         "otherwise -> NEEDS_MORE_INFORMATION"],
        "decision_to_workflow_state": {k: v.value for k, v in AUTOMATED_TO_STATE.items()},
        "required_confirmations": sorted(c.value for c in REQUIRED_CHECKS),
        "independent_contact_sources": sorted(s.value for s in INDEPENDENT_SOURCES),
        "activation": "VERIFIED_ACTIVE only through recorded independent confirmations of all required checks; "
                      "never set by automated verification or by a reviewer directly",
        "fraud_detection_definition": "FLAG_FOR_REVIEW or REJECTED. NEEDS_MORE_INFORMATION and "
                                      "ELIGIBLE_PENDING_CONFIRMATION are never counted as detections.",
        "review_bases": ["DETERMINISTIC_FINDING", "DOCUMENT_SUPPORTED_MODEL_FINDING", "UNVERIFIED_MODEL_SUSPICION"],
        "gemini_dependent_checks": GEMINI_DEPENDENT,
        "development_conventions": {
            "retrieval": "frozen lexical top-5 (evaluation/gemini_evaluation_framework.py lexical_retrieve, top_k=5); "
                         "no embedding calls. Production uses embedding retrieval (app/services/rag.py).",
            "reference_date_live": "today in Asia/Kolkata at run time (run_date_aware_dev_eval.reference_date)",
            "reference_date_offline": "submitted_on, else the latest document date, else a fixed fallback date",
        },
        "independent_evaluation_parameters": "NOT PART OF THIS FREEZE. Model, retrieval, reference-date rule, budget "
                                             "and stopping rules are fixed in the sealed v5 protocol after approval "
                                             "(evaluation/independent_test_protocol_v5.md).",
    }


# ------------------------------------------------------------------ tests
def test_results() -> dict:
    import os
    env = {**os.environ, "GEMINI_API_KEY": ""}     # belt and braces: tests/conftest.py also blanks the key
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"],
                             capture_output=True, text=True, cwd=ROOT, env=env)
        cases = list(ET.parse(junit).getroot().iter("testcase"))
    def tid(c):
        return f"{c.get('classname')}::{c.get('name')}"
    failed = sorted(tid(c) for c in cases if c.find("failure") is not None or c.find("error") is not None)
    skipped = sorted(tid(c) for c in cases if c.find("skipped") is not None)
    hybrid = [c for c in cases if c.get("classname", "").startswith("tests.test_hybrid_v3")]
    repro = subprocess.run([sys.executable, "evaluation/check_frozen_benchmark_reproducibility.py"],
                           capture_output=True, text=True, cwd=ROOT, env=env)
    repro_json = json.loads(repro.stdout)
    from freeze_hybrid_v2 import verify as verify_v2
    from verify_candidate_v3_freeze import verify as verify_v3
    return {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python -m pytest -q -p no:cacheprovider (GEMINI_API_KEY blanked; conftest forces the local fallback)",
        "full_suite": {"collected": len(cases), "passed": len(cases) - len(failed) - len(skipped),
                       "failed": failed, "skipped": len(skipped), "exit_code": run.returncode,
                       "unexpected_failures": sorted(set(failed) - KNOWN_FAILURES),
                       "known_failures": {"tests.test_campaigns::test_campaign_verification_endpoint":
                                          "pre-existing HTTP 401 in the campaign verification endpoint test; "
                                          "unrelated to the development packages"}},
        "hybrid_v3_tests": {"collected": len(hybrid),
                            "failed": sorted(tid(c) for c in hybrid if c.find("failure") is not None
                                             or c.find("error") is not None)},
        "frozen_benchmark_reproducibility": {
            "command": "python evaluation/check_frozen_benchmark_reproducibility.py", "exit_code": repro.returncode,
            "all_reproduced": repro_json.get("all_reproduced"),
            "details": {k: ({kk: vv for kk, vv in v.items() if kk in ("cases", "reproduced", "mismatches", "valid", "changed")}
                            if isinstance(v, dict) else v) for k, v in repro_json.items()}},
        "frozen_v3_freeze_valid": verify_v3()["valid"],
        "hybrid_v2_freeze": verify_v2(),
    }


# ------------------------------------------------------------------ git and environment
def git_state() -> dict:
    def last(*paths):
        return git("log", "-1", "--format=%H", "--", *paths)
    recorded = [p for paths in recorded_paths().values() for p in paths]
    return {
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head_at_freeze": git("rev-parse", "HEAD"),
        "upstream": git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or None,
        "main": git("rev-parse", "main"),
        "origin_main_local_ref": git("rev-parse", "origin/main"),
        "recorded_files_uncommitted": git("status", "--porcelain", "--", *recorded).splitlines(),
        "commits": {
            "hybrid_v3_code": last(PACKAGE),
            "hybrid_v3_report": last("docs/hybrid_v3_safety_changes.md"),
            "hybrid_v2_freeze": last("evaluation/hybrid_v2_freeze.json"),
            "frozen_v3_freeze": last("evaluation/development_candidate_v3_freeze.json"),
            "production_path_files_last_changed_on_this_branch": last(*PRODUCTION_PATH),
            "date_aware_live_results": last("evaluation/runs/date_aware_dev_eval_live"),
        },
    }


def environment() -> dict:
    versions = {}
    for name in ("pydantic", "httpx", "fastapi", "pytest", "python-dotenv", "SQLAlchemy"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    requirements = ROOT / "requirements.txt"
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions,
            "requirements_txt_sha256": sha_bytes(requirements.read_bytes()) if requirements.exists() else None}


KNOWN_LIMITATIONS = [
    "Development evidence only. Every number so far is in-sample: the 750 benchmark cases, the 10 historical cases, the "
    "8 date-aware cases and the test fixtures were all inspected during development; none can be reused as independent "
    "test data.",
    "In-sample adjustments were made to the financial-document classifier after inspecting benchmark outcomes (see "
    "docs/hybrid_v3_safety_changes.md, 'Disclosed development adjustments').",
    "Fabricated but internally consistent dossiers pass every automated check; only independent external confirmation "
    "stops them, and the confirmation pilot has not been run.",
    "Insider-issued false documents from genuine institutions cannot be detected from text.",
    "The requested amount is not independently confirmed as a separate, recorded step. For medical and education "
    "campaigns the institution check's description includes the billed amount or fee demand, but the outcome records no "
    "amount; for community and organisation campaigns the institution check confirms registration only.",
    "Final approval and activation are one state (VERIFIED_ACTIVE) in the frozen workflow; disbursement is allowed in it.",
    "Contradictions listed in gemini_dependent_checks depend on Gemini or a reviewer. Gemini 3.6 Flash on the free tier "
    "returned 1 valid answer in 4 HTTP requests in the last live run (2 server errors, 1 quota error).",
    "Requiring formal cost evidence increases information requests for genuine applicants without formal quotations "
    "(benchmarks, in-sample: information requests 336 -> 460, legitimate approvals 231 -> 162).",
    "Deterministic parsers were developed on clean synthetic English text; scans, OCR noise, regional languages and "
    "unusual date formats are untested.",
    "Thresholds (5% amount tolerance, 2-day date tolerance, 1-year age tolerance, 365-day staleness, traceability 2 of "
    "4) are reasoned defaults, not calibrated values.",
    "Frozen V3's SERVICE_UNRELATED lexicon does not link synonyms such as 'palatoplasty' and 'cleft palate repair' "
    "(DA-04 receives an information request).",
    "Development retrieval was lexical top-5 with no embeddings; production retrieval uses embeddings. Cases with more "
    "than five chunks would be retrieved differently.",
    "370 benchmark cases have no submission date; their offline decisions depend on the reference date, so the "
    "behavioural fingerprint pins a fixed fallback date (2026-11-17).",
]


# ------------------------------------------------------------------ commands
def freeze():
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.name} already exists; a frozen implementation is never re-frozen in place")
    state = git_state()
    if state["recorded_files_uncommitted"]:
        raise SystemExit(f"Refusing to freeze: recorded files have uncommitted changes {state['recorded_files_uncommitted']}")
    tests = test_results()
    problems = []
    if tests["full_suite"]["unexpected_failures"] or tests["hybrid_v3_tests"]["failed"]:
        problems.append(f"unexpected test failures {tests['full_suite']['unexpected_failures']}")
    if not tests["frozen_benchmark_reproducibility"]["all_reproduced"]:
        problems.append("frozen benchmarks do not reproduce")
    if not (tests["frozen_v3_freeze_valid"] and tests["hybrid_v2_freeze"]["valid"]):
        problems.append("an earlier freeze does not verify")
    if problems:
        raise SystemExit("Refusing to freeze:\n- " + "\n- ".join(problems))
    from app.services.development_hybrid_v3 import POLICY_VERSION
    now = datetime.now(timezone.utc)
    manifest = {
        "candidate": "hybrid v3 (development evaluation candidate only; not approved for production)",
        "policy_version": POLICY_VERSION,
        "frozen_at_utc": now.isoformat(), "frozen_at_asia_kolkata": now.astimezone(IST).isoformat(),
        "git": state,
        "files": current_hashes(),
        "model_and_prompt": prompt_configuration(),
        "evaluation_configuration": evaluation_configuration(),
        "behavioural_fingerprint": behavioural_fingerprint(),
        "test_results": tests,
        "environment": environment(),
        "known_limitations": KNOWN_LIMITATIONS,
        "development_data_excluded_from_independent_testing": {
            "benchmarks_750": BENCHMARKS, "historical_10": "evaluation/gemini_eval_v1/cases.jsonl",
            "date_aware_8": "evaluation/date_aware_dev_eval/scenarios.json",
            "development_sets": ["evaluation/development_scenarios_v1.jsonl", "evaluation/development_scenarios_v2.jsonl",
                                 "evaluation/development_scenarios_v3.jsonl",
                                 "evaluation/development_scenarios_v3_contradiction_only.jsonl",
                                 "evaluation/development_scenarios_v3_initial.jsonl"],
            "test_fixtures": ["tests/test_hybrid_v3.py", "tests/test_hybrid_v2.py"]},
        "api_calls_made_by_this_freeze": 0,
        "rule": "Any change to a recorded file invalidates independent-test results for this candidate. A changed "
                "version needs a new freeze and a new, unseen test set. Defects found during the independent test are "
                "reported, not fixed. Do not tune against the independent test.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "files": sum(len(v) for v in manifest["files"].values()),
                      "head_at_freeze": state["head_at_freeze"],
                      "behavioural_fingerprint": manifest["behavioural_fingerprint"]["sha256"]}, indent=2))


def verify() -> dict:
    from freeze_hybrid_v2 import verify as verify_v2
    from verify_candidate_v3_freeze import verify as verify_v3
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    now = current_hashes()
    changed, added = [], []
    for group, files in manifest["files"].items():
        changed += [p for p, h in files.items() if not (ROOT / p).exists() or now.get(group, {}).get(p) != h]
        added += sorted(set(now.get(group, {})) - set(files))
    prompt = prompt_configuration()
    recorded_prompt = manifest["model_and_prompt"]
    prompt_same = all(prompt[k] == recorded_prompt[k] for k in ("generation_config", "response_schema_sha256",
                                                                 "endpoint_template", "fingerprint"))
    behaviour = behavioural_fingerprint()
    behaviour_changed = sorted(k for k, v in behaviour["sets"].items()
                               if v["sha256"] != manifest["behavioural_fingerprint"]["sets"][k]["sha256"])
    config_same = sha_json(evaluation_configuration()) == sha_json(manifest["evaluation_configuration"])
    v3_valid, v2 = verify_v3()["valid"], verify_v2()
    valid = not changed and not added and prompt_same and not behaviour_changed and config_same and v3_valid and v2["valid"]
    return {"valid": valid, "changed": changed, "added": added, "prompt_configuration_unchanged": prompt_same,
            "evaluation_configuration_unchanged": config_same, "behaviour_changed_sets": behaviour_changed,
            "behavioural_fingerprint": behaviour["sha256"], "frozen_v3_freeze_valid": v3_valid,
            "hybrid_v2_freeze_valid": v2["valid"], "policy_version": manifest["policy_version"]}


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "freeze":
        freeze()
    else:
        result = verify()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["valid"] else 1)
