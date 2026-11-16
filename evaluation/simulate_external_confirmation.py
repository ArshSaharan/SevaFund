"""Monte Carlo simulation of the external-confirmation step, driving the REAL workflow code.

THIS IS A SIMULATION, NOT A MEASUREMENT.  Every number it produces follows from the
assumed contact behaviour in `SCENARIOS`; none of it describes real hospitals, schools,
registries, banks or verifiers.  Its purpose is to
  * exercise app/services/development_approval_workflow end to end, at scale, with
    unreachable contacts, false contact details, careless verifiers, spoofed directories
    and insider collusion;
  * show which assumptions decide safety (fraud activation) and workload;
  * produce attempt logs in the same format a real confirmation pilot will record, so
    confirmation_metrics.py can be validated before real data exist.

Population: campaigns that frozen V3 + the workflow send to ELIGIBLE_PENDING_CONFIRMATION, taken from
saved predictions (no verifier is executed).
"""
import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.development_approval_workflow import (
    AutomatedOutcome, ConfirmationCheck, ConfirmationOutcome, ConfirmationRecord, ContactSource, WorkflowState,
    record_confirmation, start,
)
from confirmation_metrics import confirmation_metrics

C, O, S = ConfirmationCheck, ConfirmationOutcome, WorkflowState
RUNS = Path(__file__).with_name("runs")
BASE_TIME = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
POPULATIONS = {
    "final_test_300": ("final_test_v3_31f16ae955c4/case_level_predictions.csv", "final_test_scenarios_v3.jsonl",
                       "V3_frozen", None),
    "prior_150": ("diagnostic_v3_prior_benchmarks_ba1b045e8b9d/case_level_predictions.csv",
                  "independent_test_150.jsonl", "V3", "independent_test_150"),
}


@dataclass
class Assumptions:
    """Per-attempt probabilities and effort.  All values are assumptions to be replaced by pilot data."""
    p_unreachable: float = 0.25                  # an independent contact does not answer this attempt
    p_legit_record_mismatch: float = 0.02        # genuine campaign, institution record disagrees (clerical error)
    p_fraud_kyc_pass: float = 0.7                # fraudster passes beneficiary KYC (own or borrowed identity)
    p_fraud_payee_lookalike: float = 0.2         # fraud payout account passes bank account-holder name match
    p_spoofed_directory: float = 0.02            # the "independent" directory entry was planted by the fraudster
    p_insider_collusion: float = 0.02            # someone at the institution confirms a fabricated record
    p_fraud_fake_contact: float = 0.8            # fraud campaign supplies a confederate's "institution" contact
    p_fake_contact_printed: float = 0.7          # ... printed in the uploads (else sent out of band)
    p_legit_wrong_contact: float = 0.05          # genuine campaign supplies an outdated institution contact
    p_careless_verifier: float = 0.10            # verifier first calls the campaign-supplied number, logs it as directory
    p_borderline_inconclusive: float = 0.5       # institution cannot yet confirm an unresolved claim
    median_response_hours: Dict[str, float] = field(default_factory=lambda: {
        "BENEFICIARY": 2.0, "PAYMENT_DESTINATION": 4.0, "INSTITUTION": 24.0})
    minutes_per_attempt: Dict[str, float] = field(default_factory=lambda: {
        "BENEFICIARY": 3.0, "PAYMENT_DESTINATION": 3.0, "INSTITUTION": 15.0})
    retry_after_hours: float = 24.0
    max_attempts_per_check: int = 3
    horizon_days: float = 14.0


SCENARIOS = {
    "reference": Assumptions(),
    "careful_verifiers": Assumptions(p_careless_verifier=0.0),
    "low_responsiveness": Assumptions(p_unreachable=0.5),
    "adversarial": Assumptions(p_spoofed_directory=0.10, p_insider_collusion=0.05, p_fraud_payee_lookalike=0.5,
                               p_fraud_kyc_pass=0.9, p_careless_verifier=0.2, p_fake_contact_printed=0.4),
}
SOURCE_FOR = {C.BENEFICIARY: ContactSource.PLATFORM_KYC, C.PAYMENT_DESTINATION: ContactSource.PLATFORM_KYC,
              C.INSTITUTION: ContactSource.OFFICIAL_DIRECTORY}


def load_population(name: str) -> List[dict]:
    predictions, dataset, engine, dataset_filter = POPULATIONS[name]
    meta = {}
    for line in Path(__file__).with_name(dataset).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            meta[row["case_id"]] = row
    pending = []
    for row in csv.DictReader((RUNS / predictions).open(encoding="utf-8")):
        if row["engine"] != engine or (dataset_filter and row.get("dataset") != dataset_filter):
            continue
        case = meta[row["case_id"]]
        outcome = AutomatedOutcome(decision=row["decision"], category=row["category"],
                                   beneficiary_type=case["input"].get("beneficiary_type"))
        if start(outcome).state == S.ELIGIBLE_PENDING_CONFIRMATION:
            pending.append({"campaign_id": row["case_id"], "label": row["ground_truth"], "outcome": outcome})
    return pending


def _truth(label: str, check: C, a: Assumptions, rng: random.Random, compromised: bool) -> O:
    """What the genuinely independent party would say."""
    if label == "fraudulent":
        if check == C.BENEFICIARY:
            return O.CONFIRMED if rng.random() < a.p_fraud_kyc_pass else O.CONTRADICTED
        if check == C.PAYMENT_DESTINATION:
            return O.CONFIRMED if rng.random() < a.p_fraud_payee_lookalike else O.CONTRADICTED
        return O.CONFIRMED if compromised else O.CONTRADICTED
    if label == "borderline" and check == C.INSTITUTION and rng.random() < a.p_borderline_inconclusive:
        return O.INCONCLUSIVE
    if label != "fraudulent" and check == C.INSTITUTION and rng.random() < a.p_legit_record_mismatch:
        return O.CONTRADICTED
    return O.CONFIRMED


def simulate_campaign(campaign: dict, a: Assumptions, rng: random.Random, run: int):
    label = campaign["label"]
    record = start(campaign["outcome"])
    fake_contact = (label == "fraudulent" and rng.random() < a.p_fraud_fake_contact) or \
                   (label != "fraudulent" and rng.random() < a.p_legit_wrong_contact)
    printed = fake_contact and rng.random() < a.p_fake_contact_printed
    supplied_number = f"+91 9{rng.randrange(10**8, 10**9)}"
    campaign_text = f"For confirmation call the hospital desk on {supplied_number}." if printed else "No contact printed."
    compromised = label == "fraudulent" and (rng.random() < a.p_spoofed_directory or rng.random() < a.p_insider_collusion)
    events = []                                   # (hour, check, attempt, origin, outcome, minutes)
    for check in list(record.pending_checks):
        hour, truth = 0.0, _truth(label, check, a, rng, compromised)
        if check == C.INSTITUTION and fake_contact and rng.random() < a.p_careless_verifier:
            # The verifier rings the campaign-supplied number first and mislabels it as the directory number.
            reply = O.CONFIRMED if label == "fraudulent" else O.UNREACHABLE
            hour += rng.lognormvariate(math.log(a.median_response_hours[check.value]), 0.8)
            events.append((hour, check, 0, "campaign_printed" if printed else "campaign_out_of_band", reply,
                           a.minutes_per_attempt[check.value]))
        for attempt in range(1, a.max_attempts_per_check + 1):
            hour += rng.lognormvariate(math.log(a.median_response_hours[check.value]), 0.8)
            reply = O.UNREACHABLE if rng.random() < a.p_unreachable else truth
            events.append((hour, check, attempt, "independent", reply, a.minutes_per_attempt[check.value]))
            if reply != O.UNREACHABLE:
                break
            hour += a.retry_after_hours
    attempts, activated_at, flagged_at = [], None, None
    for hour, check, attempt, origin, reply, minutes in sorted(events, key=lambda e: e[0]):
        if hour > a.horizon_days * 24 or record.state != S.ELIGIBLE_PENDING_CONFIRMATION:
            continue
        if check not in record.pending_checks:
            continue                              # already satisfied: a verifier would not call again
        reference = supplied_number if origin != "independent" else f"directory-{check.value.lower()}"
        before = set(record.pending_checks)
        record = record_confirmation(record, ConfirmationRecord(
            check=check, outcome=reply, contact_source=SOURCE_FOR[check], contact_reference=reference,
            verifier_id="sim", recorded_at=BASE_TIME + timedelta(hours=hour)), campaign_text=campaign_text)
        counted = check in before and check not in set(record.pending_checks)
        attempts.append({"run": run, "campaign_id": campaign["campaign_id"], "label": label, "check": check.value,
                         "attempt": attempt, "contact_origin": origin,
                         "contact_source": record.confirmations[-1].contact_source.value, "outcome": reply.value,
                         "counted": counted, "false_contact_detail": fake_contact and check == C.INSTITUTION,
                         "hours_elapsed": round(hour, 2), "minutes_spent": minutes})
        if record.state == S.VERIFIED_ACTIVE:
            activated_at = hour
        elif record.state == S.FLAG_FOR_REVIEW:
            flagged_at = hour
    outcome = {"run": run, "campaign_id": campaign["campaign_id"], "label": label, "final_state": record.state.value,
               "hours_to_activation": None if activated_at is None else round(activated_at, 2),
               "hours_to_flag": None if flagged_at is None else round(flagged_at, 2),
               "compromised_independent_channel": compromised}
    return attempts, outcome


def simulate(population: List[dict], a: Assumptions, replications: int, seed: int):
    per_run = []
    all_attempts, all_outcomes = [], []
    for run in range(replications):
        rng = random.Random(seed * 1000 + run)
        attempts, outcomes = [], []
        for campaign in population:
            log, outcome = simulate_campaign(campaign, a, rng, run)
            attempts += log
            outcomes.append(outcome)
        per_run.append(confirmation_metrics(attempts, outcomes))
        if run == 0:
            all_attempts, all_outcomes = attempts, outcomes
    return per_run, all_attempts, all_outcomes


def _interval(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return {"mean": round(sum(values) / len(values), 3),
            "p2.5": values[int(0.025 * (len(values) - 1))], "p97.5": values[int(0.975 * (len(values) - 1))]}


KEY_METRICS = {
    "fraud prevented from activation (rate)": lambda m: m["fraud_prevention"]["prevention_rate"],
    "fraud activated (campaigns)": lambda m: m["fraud_prevention"]["activated"],
    "legitimate activated within horizon (rate)": lambda m: m["legitimate_outcomes"]["activation_rate"],
    "legitimate wrongly flagged (campaigns)": lambda m: m["legitimate_outcomes"]["wrongly_flagged"],
    "still pending at horizon (campaigns)": lambda m: m["unsuccessful_verification_attempts"]["campaigns_still_pending_at_horizon"],
    "successful independent confirmations (count)": lambda m: m["successful_independent_confirmations"]["count"],
    "unsuccessful attempts (count)": lambda m: m["unsuccessful_verification_attempts"]["count"],
    "campaigns with false institution contact": lambda m: m["false_institution_contact_details"]["campaigns_with_false_contact_detail"],
    "campaign-supplied contacts used by verifiers": lambda m: m["false_institution_contact_details"]["campaign_supplied_contacts_used_by_verifiers"],
    "... caught by upload contact matching": lambda m: m["false_institution_contact_details"]["of_which_caught_by_upload_contact_matching"],
    "... accepted towards activation": lambda m: m["false_institution_contact_details"]["of_which_accepted_towards_activation"],
    "median hours to activation (legitimate)": lambda m: (m["confirmation_time_hours"]["to_activation_legitimate"] or {}).get("median"),
    "mean hours to activation (legitimate)": lambda m: (m["confirmation_time_hours"]["to_activation_legitimate"] or {}).get("mean"),
    "verification attempts per campaign": lambda m: m["administrative_workload"]["attempts_per_campaign"],
    "verifier minutes per campaign": lambda m: m["administrative_workload"]["verifier_minutes_per_campaign"],
}


def render(report) -> str:
    lines = ["# External-confirmation workflow — SIMULATION (not a measurement)", "",
             "All figures follow from the assumed contact behaviour listed under each scenario. They test the "
             "workflow's logic and show which assumptions drive safety and workload; they say nothing about real "
             "institutions or verifiers. Replace the assumptions with confirmation-pilot data "
             "(`evaluation/confirmation_pilot_protocol.md`).", "",
             "Mean over replications, with the 2.5–97.5 percentile range in brackets.", ""]
    for population, data in report["populations"].items():
        lines += [f"## Population: {population}", "",
                  f"Campaigns entering confirmation: {data['campaigns']} ({data['labels']}). "
                  f"Replications per scenario: {report['replications']}.", "",
                  "| Metric | " + " | ".join(data["scenarios"]) + " |", "|---|" + "---:|" * len(data["scenarios"])]
        for metric in KEY_METRICS:
            cells = []
            for scenario in data["scenarios"].values():
                v = scenario["summary"][metric]
                cells.append("—" if v is None else f"{v['mean']:g} [{v['p2.5']:g}–{v['p97.5']:g}]")
            lines.append(f"| {metric} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## Assumptions per scenario", ""]
    for name, assumptions in report["assumptions"].items():
        lines += [f"**{name}**: `{json.dumps(assumptions)}`", ""]
    lines += ["## What the simulation shows about the workflow logic", "",
              "* Campaign-supplied contacts never count towards activation, including when a careless verifier "
              "mislabels a number printed in the uploads (caught by upload contact matching).",
              "* A campaign-supplied number sent *out of band* (not in the uploads) and mislabelled by a careless "
              "verifier is indistinguishable from an independent contact; in that case a confederate can confirm. "
              "This is the residual human-process risk the policy cannot close by itself.",
              "* With honest independent channels, fraud reaches VERIFIED_ACTIVE only when the independent channel "
              "itself is compromised (spoofed directory entry or insider collusion) *and* KYC and payee checks pass.",
              ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--replications", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "simulation": True, "replications": args.replications,
              "seed": args.seed, "assumptions": {k: asdict(v) for k, v in SCENARIOS.items()}, "populations": {},
              "workflow_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                  sorted((ROOT / "app/services/development_approval_workflow").glob("*.py"))}}
    target = args.output_dir or RUNS / f"confirmation_simulation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    logs = {}
    for population_name in POPULATIONS:
        population = load_population(population_name)
        labels = defaultdict(int)
        for campaign in population:
            labels[campaign["label"]] += 1
        scenarios = {}
        for scenario_name, assumptions in SCENARIOS.items():
            per_run, attempts, outcomes = simulate(population, assumptions, args.replications, args.seed)
            scenarios[scenario_name] = {"summary": {metric: _interval([f(m) for m in per_run])
                                                    for metric, f in KEY_METRICS.items()},
                                        "first_replication": per_run[0]}
            logs[f"attempt_log_{population_name}_{scenario_name}_run0.csv"] = attempts
        report["populations"][population_name] = {"campaigns": len(population), "labels": dict(labels),
                                                  "scenarios": scenarios}
    target.mkdir(parents=True, exist_ok=False)            # written only after every scenario completed
    for filename, attempts in logs.items():
        with (target / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(attempts[0]))
            writer.writeheader()
            writer.writerows(attempts)
    (target / "results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    (target / "report.md").write_text(render(report))
    print(target)
    return report


if __name__ == "__main__":
    main()
