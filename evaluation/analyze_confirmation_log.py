"""Analyze a REAL confirmation-pilot log by replaying it through the workflow code.

Inputs (CSV; templates in evaluation/confirmation_pilot/):
  campaigns.csv  campaign_id, label (if known, else blank), category, beneficiary_type,
                 contacts_in_uploads (semicolon-separated phone numbers / e-mails printed in the uploads),
                 supplied_contact_matches_directory (yes | no | blank: campaign gave no institution contact)
  attempts.csv   campaign_id, check, attempt, contact_origin, contact_source, contact_reference,
                 outcome, started_at, finished_at, minutes_spent, verifier_id, notes

Replaying through app.services.development_approval_workflow guarantees the pilot is scored with exactly
the rules the system enforces: which confirmations count, when a campaign activates, when it is flagged.
contact_reference may be the raw contact (kept locally) - it is never written to the output, which
contains only aggregate metrics.
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.development_approval_workflow import (
    AutomatedOutcome, ConfirmationCheck, ConfirmationOutcome, ConfirmationRecord, ContactSource, WorkflowState,
    record_confirmation, start,
)
from confirmation_metrics import confirmation_metrics

S = WorkflowState


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def replay(campaign_rows, attempt_rows):
    by_campaign = {}
    for row in attempt_rows:
        by_campaign.setdefault(row["campaign_id"], []).append(row)
    attempts_out, campaigns_out = [], []
    for campaign in campaign_rows:
        record = start(AutomatedOutcome(decision="APPROVED", category=campaign["category"],
                                        beneficiary_type=campaign.get("beneficiary_type") or "SELF"))
        uploads_text = " ".join((campaign.get("contacts_in_uploads") or "").split(";"))
        rows = sorted(by_campaign.get(campaign["campaign_id"], []), key=lambda r: _time(r["finished_at"]))
        first = _time(rows[0]["started_at"]) if rows else None
        activated, flagged = None, None
        for row in rows:
            if record.state != S.ELIGIBLE_PENDING_CONFIRMATION:
                break                                   # later attempts after a decision are not replayed
            check = ConfirmationCheck(row["check"])
            before = set(record.pending_checks)
            record = record_confirmation(record, ConfirmationRecord(
                check=check, outcome=ConfirmationOutcome(row["outcome"]), contact_source=ContactSource(row["contact_source"]),
                contact_reference=row.get("contact_reference", ""), verifier_id=row.get("verifier_id") or "pilot",
                recorded_at=_time(row["finished_at"])), campaign_text=uploads_text)
            hours = round((_time(row["finished_at"]) - first).total_seconds() / 3600, 2)
            attempts_out.append({
                "campaign_id": campaign["campaign_id"], "label": campaign.get("label") or None, "check": check.value,
                "attempt": int(row["attempt"]), "contact_origin": row["contact_origin"],
                "contact_source": record.confirmations[-1].contact_source.value, "outcome": row["outcome"],
                "counted": check in before and check not in record.pending_checks,
                "false_contact_detail": (campaign.get("supplied_contact_matches_directory") or "").strip().lower() == "no"
                and check == ConfirmationCheck.INSTITUTION, "hours_elapsed": hours,
                "minutes_spent": float(row.get("minutes_spent") or 0)})
            if record.state == S.VERIFIED_ACTIVE:
                activated = hours
            elif record.state == S.FLAG_FOR_REVIEW:
                flagged = hours
        campaigns_out.append({"campaign_id": campaign["campaign_id"], "label": campaign.get("label") or None,
                              "final_state": record.state.value, "hours_to_activation": activated,
                              "hours_to_flag": flagged})
    return attempts_out, campaigns_out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("campaigns", type=Path)
    parser.add_argument("attempts", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    campaigns = list(csv.DictReader(args.campaigns.open(encoding="utf-8")))
    attempts = list(csv.DictReader(args.attempts.open(encoding="utf-8")))
    replayed_attempts, replayed_campaigns = replay(campaigns, attempts)
    metrics = confirmation_metrics(replayed_attempts, replayed_campaigns)
    text = json.dumps(metrics, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return metrics


if __name__ == "__main__":
    main()
