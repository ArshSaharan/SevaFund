"""Final offline checks before the kit is sealed.  No API call and no network: every check is local.

    check(registry=None, rerun_statistics=True, run_tests=True) -> report

The report separates FAILED checks (something is wrong with the tooling or the pre-registration) from BLOCKING
requirements (owner decisions or recruitment not yet done).  The kit can be sealed only with a report that has neither,
written for exactly the current kit files (`kit.seal` checks the hashes).  Run it again immediately before sealing.
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import config, exclusion, kit, packets, participants, scorer

APPROVAL_KEY = "criteria_review_2026_11_17"

# Pre-specified acceptance bounds for the Monte Carlo validation (2,000 simulations per scenario; the Monte Carlo
# standard error of a coverage near 0.95 is about 0.005, so 0.935 is three standard errors below nominal).
STATISTICAL_ACCEPTANCE = {
    "primary_interval_min_coverage": 0.935,          # deff_kish_floor_0.1, every design and scenario
    "bootstrap_min_coverage": 0.92,                  # secondary interval
    "paired_test_max_type1": 0.05,                   # cluster sign-flip, every scenario
    "paired_difference_min_coverage": 0.93,
}
PRIMARY_METHOD = "deff_kish_floor_0.1"
SUBPROCESS_ENV_DROP = ("GEMINI_API_KEY", "GOOGLE_API_KEY", config.APPROVAL_ENV)


def snapshot_values(prereg: dict) -> dict:
    sc = prereg["success_criteria"]
    full_row = {"activated": True, "activation_allowed": True, "final_approved": True, "pending_checks": [],
                "documentation": "complete", "truth": "legitimate", "satisfied": [], "confirmation_records": 3,
                "campaign_supplied_satisfied": 0, "activation_triggers": ["confirmation"]}
    scorer_types = "".join(sorted(scorer.unsafe_activation(full_row)))
    prereg_types = "abcde" if "(a)-(e)" in sc["gates"]["G2_no_unsafe_activation"] else "incomplete"
    return {
        "H1_threshold": sc["primary_endpoint"]["H1_dossier_detectable_fraud_recall_minimum"]["threshold"],
        "R1_threshold": sc["research_target"]["R1_dossier_detectable_fraud_recall_target"]["threshold"],
        "K1_threshold": sc["key_secondary"]["K1_false_positive_rate"]["threshold"],
        "K2_threshold": sc["key_secondary"]["K2_legitimate_complete_approval"]["threshold"],
        "fairness_margin": sc["fairness_noninferiority"]["margin"],
        "genuine_but_informal_min_groups_per_category":
            prereg["design"]["incomplete_subtype_min_groups_per_category"]["genuine_but_informal"],
        "G2_unsafe_activation_types": prereg_types if prereg_types == scorer_types else f"prereg {prereg_types}, scorer {scorer_types}",
        "cluster_size_rule": prereg["analysis"]["cluster_size_rule"],
        "icc_floor": prereg["analysis"]["icc_floor"],
        "comparison_adjustment": sc["comparisons_with_hybrid_v2"]["adjustment"],
        "paired_test_family": sc["comparisons_with_hybrid_v2"]["test"],
    }


def snapshot_problems(prereg: dict) -> List[str]:
    approval = prereg.get("owner_approvals", {}).get(APPROVAL_KEY)
    if not approval:
        return ["the owner's criteria approval is not recorded in the pre-registration"]
    expected, actual = approval["criteria_snapshot"], snapshot_values(prereg)
    problems = [f"{k}: approved {expected.get(k)!r}, pre-registration has {actual.get(k)!r}"
                for k in sorted(set(expected) | set(actual)) if expected.get(k) != actual.get(k)]
    if not prereg["success_criteria"].get("verdict_scope"):
        problems.append("verdict_scope (not production readiness) is missing")
    if "scope" not in prereg["success_criteria"]["key_secondary"]["K2_legitimate_complete_approval"]:
        problems.append("K2 is not scoped as a preliminary floor")
    if not prereg.get("owner_approvals", {}).get("known_weakness_commitment"):
        problems.append("the G2 non-weakening commitment is missing")
    return problems


def provider_and_budget_problems(prereg: dict) -> List[str]:
    problems = []
    if prereg["model"]["availability_verified"] is not False and not prereg["model"].get("availability_evidence_owner"):
        problems.append("model availability is marked verified without recorded owner evidence")
    if prereg["api_usage"]["quota_verified"] is not False and not prereg["api_usage"].get("quota_evidence_owner"):
        problems.append("free-tier quota is marked verified without recorded owner evidence")
    if prereg["api_usage"]["paid_usage_allowed"] is not False:
        problems.append("paid usage is enabled")
    if prereg["api_usage"]["approved_requests"] != 0:
        problems.append("the pre-registration itself approves requests; approvals belong in a separate written file")
    if prereg["model"]["substitution_allowed"] is not False:
        problems.append("model substitution is allowed")
    return problems


def statistics_problems(record: dict) -> List[str]:
    a, problems = STATISTICAL_ACCEPTANCE, []
    primary = [r["coverage"] for r in record["proportion_coverage"] if r["method"] == PRIMARY_METHOD]
    if not primary or min(primary) < a["primary_interval_min_coverage"]:
        problems.append(f"primary interval coverage {min(primary) if primary else None} < {a['primary_interval_min_coverage']}")
    boot = [r["coverage"] for r in record["bootstrap_coverage"]]
    if not boot or min(boot) < a["bootstrap_min_coverage"]:
        problems.append(f"bootstrap coverage {min(boot) if boot else None} < {a['bootstrap_min_coverage']}")
    type1 = [r["type1_cluster_sign_flip"] for r in record["paired_type1"]]
    if not type1 or max(type1) > a["paired_test_max_type1"]:
        problems.append(f"cluster sign-flip type I error {max(type1) if type1 else None} > {a['paired_test_max_type1']}")
    diff = [r["coverage"] for r in record["paired_difference_coverage"]]
    if not diff or min(diff) < a["paired_difference_min_coverage"]:
        problems.append(f"paired-difference coverage {min(diff) if diff else None} < {a['paired_difference_min_coverage']}")
    return problems


def statistics_summary(record: dict) -> dict:
    primary = [r["coverage"] for r in record["proportion_coverage"] if r["method"] == PRIMARY_METHOD]
    naive = [r["coverage"] for r in record["proportion_coverage"] if r["method"] == "naive_wilson"]
    return {"primary_interval_coverage_min": min(primary), "primary_interval_scenarios": len(primary),
            "naive_wilson_coverage_min": min(naive),
            "bootstrap_coverage_min": min(r["coverage"] for r in record["bootstrap_coverage"]),
            "cluster_sign_flip_type1_max": max(r["type1_cluster_sign_flip"] for r in record["paired_type1"]),
            "mcnemar_ignoring_groups_type1_max": max(r["type1_exact_mcnemar_ignoring_groups"] for r in record["paired_type1"]),
            "paired_difference_coverage_min": min(r["coverage"] for r in record["paired_difference_coverage"])}


def rerun_statistics() -> dict:
    from . import ci_validation
    fresh = ci_validation.run_all(quick=False)
    fresh["coverage_summary"] = ci_validation.summarise_coverage(fresh["proportion_coverage"])
    committed = json.loads((config.KIT / "statistical_validation.json").read_text(encoding="utf-8"))
    differing = sorted(k for k in set(fresh) | set(committed) if fresh.get(k) != committed.get(k))
    return {"reproduced": not differing, "differing_sections": differing}


def _clean_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in SUBPROCESS_ENV_DROP}
    env["GEMINI_API_KEY"] = ""
    return env


def tooling_tests() -> dict:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_independent_v5.py"],
                          cwd=config.ROOT, capture_output=True, text=True, env=_clean_env())
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr.strip()[-300:]
    return {"passed": proc.returncode == 0, "summary": tail}


def packet_problems() -> List[str]:
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        for role in packets.PACKETS:
            built = packets.build(role, Path(tmp) / role)
            allowed = set(packets.PACKETS[role]) | {"README.md"}
            if set(built["files"]) != allowed:
                problems.append(f"{role} packet has {built['files']}")
    return problems


INDEPENDENT_CASE_ID = re.compile(r"\bT5-(?:MED|EDU|COM)-\d{4}-[A-C]\b")


def independent_cases_in_repository() -> List[str]:
    """Data files in the repository (tracked or not) that contain an independent test case ID.  None may exist before
    sealing; independent cases are stored by the coordinator outside the developers' workspace."""
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.jsonl", "*.json", "*.csv"],
                            cwd=config.ROOT, capture_output=True, text=True).stdout.split()
    return sorted(name for name in listed if (config.ROOT / name).exists()
                  and INDEPENDENT_CASE_ID.search((config.ROOT / name).read_text(encoding="utf-8", errors="ignore")))


def blocking_requirements(prereg: dict, registry: Optional[Path]) -> List[str]:
    blocking = []
    staffing = prereg["staffing"]
    design = staffing.get("design_selected")
    if registry is None:
        blocking.append("recruitment feasibility not demonstrated: no participant registry supplied")
    else:
        result = participants.feasibility(participants.load(registry), staffing)
        designs = [design] if design in result["designs"] else sorted(result["designs"])
        if not any(result["designs"][d]["feasible"] for d in designs):
            blocking.append("recruitment feasibility not demonstrated: " + "; ".join(
                f"design {d}: {', '.join(result['designs'][d]['shortfalls'])}" for d in designs))
    reduced_but_approved = design in ("C", "D") and staffing.get("reduced_design_owner_approval")
    if design not in ("A", "B") and not reduced_but_approved:
        blocking.append("no design selected by the owner (A preferred, B resource-constrained; C or D only with "
                        "explicit approval recorded as staffing.reduced_design_owner_approval)")
    if prereg["status"] != "APPROVED":
        blocking.append(f"pre-registration status is {prereg['status']}: the owner has not authorised APPROVED")
    if config.KIT_MANIFEST.exists():
        blocking.append("the kit is already sealed")
    return blocking


class NetworkGuard:
    """Blocks and records every socket connection attempted in this process while the checks run.  (The tooling
    tests run in a subprocess under their own guard against the HTTP helpers.)"""

    def __enter__(self):
        self.attempts: List[str] = []
        self._saved = (socket.socket.connect, socket.socket.connect_ex)

        def refuse(sock, address, *args):
            self.attempts.append(str(address))
            raise OSError("network access is disabled during the pre-seal check")
        socket.socket.connect = refuse
        socket.socket.connect_ex = refuse
        return self

    def __exit__(self, *exc):
        socket.socket.connect, socket.socket.connect_ex = self._saved
        return False


def check(registry: Optional[Path] = None, rerun: bool = True, run_tests: bool = True) -> dict:
    with NetworkGuard() as guard:
        report = _check(registry, rerun, run_tests)
    report["network_connections_attempted_in_process"] = guard.attempts
    if guard.attempts:
        report["failures"]["network_guard"] = guard.attempts
        report["checks"]["no_network_access"] = "FAILED"
        report["ready_to_seal"] = False
    else:
        report["checks"]["no_network_access"] = "PASSED"
    return report


def _check(registry: Optional[Path], rerun: bool, run_tests: bool) -> dict:
    prereg = config.load_prereg()
    record = json.loads((config.KIT / "statistical_validation.json").read_text(encoding="utf-8"))
    from . import runner                                        # imports the freeze verifiers (offline)
    integrity = runner.integrity()
    _, exclusion_problems, exclusion_warnings, _ = exclusion.load_prior()
    checks = {
        "criteria_match_owner_approval": snapshot_problems(prereg),
        "provider_facts_unverified_and_no_api_approval": provider_and_budget_problems(prereg),
        "statistical_validation_meets_acceptance": statistics_problems(record),
        "freezes_production_and_app_tree": [] if integrity["ok"] else [f"integrity: {integrity}"],
        "exclusion_registry": exclusion_problems,
        "participant_packets": packet_problems(),
        "no_independent_cases_in_repository": [f"independent case IDs found in {f}" for f in independent_cases_in_repository()],
    }
    details = {"statistics": statistics_summary(record), "integrity": integrity,
               "exclusion_warnings": exclusion_warnings, "acceptance_bounds": STATISTICAL_ACCEPTANCE}
    if rerun:
        details["statistics_rerun"] = rerun_statistics()
        checks["statistical_validation_reproduces"] = ([] if details["statistics_rerun"]["reproduced"] else
                                                       [f"sections differ: {details['statistics_rerun']['differing_sections']}"])
    if run_tests:
        details["tooling_tests"] = tooling_tests()
        checks["tooling_tests_pass"] = [] if details["tooling_tests"]["passed"] else [details["tooling_tests"]["summary"]]
    failed = {name: problems for name, problems in checks.items() if problems}
    blocking = blocking_requirements(prereg, registry)
    complete = rerun and run_tests
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "prereg_version": prereg["version"],
            "api_calls": 0,
            "checks": {name: ("FAILED" if name in failed else "PASSED") for name in checks},
            "failures": failed, "blocking_requirements": blocking,
            "complete_check": complete,
            "ready_to_seal": complete and not failed and not blocking,
            "registry_sha256": config.sha256_file(registry) if registry else None,
            "kit_hashes": kit.current(), "details": details}


def write_report(report: dict, out: Path) -> None:
    out = Path(out).resolve()
    for protected in (config.KIT.resolve(), config.PACKAGE.resolve()):
        if out == protected or protected in out.parents:
            raise SystemExit("Write the pre-seal report outside the kit and the tooling package (they are hashed)")
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
