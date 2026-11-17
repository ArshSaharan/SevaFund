"""Approval-safety and workload metrics for the ELIGIBLE_PENDING_CONFIRMATION workflow.

Safety and workload are reported separately.  Pending confirmation is never a
fraud detection.  External confirmation outcomes are *not* simulated as facts:
how many pending fraud cases would be caught depends on confirmation quality,
which no offline dataset measures, so it is shown only as a labelled
sensitivity analysis.
"""
from collections import Counter
from typing import Dict, List

from app.services.development_approval_workflow import AutomatedOutcome, WorkflowState, start

S = WorkflowState
MISS_RATES = (0.05, 0.2, 0.5)   # assumed share of fraudulent pending cases that confirmation fails to catch


def apply_workflow(rows: List[dict]) -> List[dict]:
    """rows need decision, category and (optionally) beneficiary_type; adds workflow fields."""
    out = []
    for row in rows:
        record = start(AutomatedOutcome(decision=row["decision"], category=row["category"],
                                        beneficiary_type=row.get("beneficiary_type") or "SELF"))
        out.append({**row, "workflow_state": record.state.value,
                    "confirmations_required": len(record.pending_checks),
                    "disbursement_allowed": record.disbursement_allowed})
    return out


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def workflow_metrics(rows: List[dict]) -> Dict:
    rows = apply_workflow(rows) if rows and "workflow_state" not in rows[0] else rows
    by = lambda label: [r for r in rows if r["ground_truth"] == label]
    fraud, legit, border = by("fraudulent"), by("legitimate"), by("borderline")
    state = lambda group, s: sum(r["workflow_state"] == s.value for r in group)
    pending_fraud = state(fraud, S.ELIGIBLE_PENDING_CONFIRMATION)
    n = len(rows)
    counts = Counter(r["workflow_state"] for r in rows)
    return {
        "state_counts": {s.value: counts.get(s.value, 0) for s in S},
        "state_by_label": {label: dict(Counter(r["workflow_state"] for r in group))
                           for label, group in (("legitimate", legit), ("fraudulent", fraud), ("borderline", border))},
        "approval_safety": {
            "automatic_activations": state(rows, S.VERIFIED_ACTIVE),
            "disbursements_allowed_without_confirmation": sum(r["disbursement_allowed"] for r in rows),
            "fraud_detected_flag_or_reject": state(fraud, S.FLAG_FOR_REVIEW) + state(fraud, S.REJECTED),
            "fraud_detection_rate": _rate(state(fraud, S.FLAG_FOR_REVIEW) + state(fraud, S.REJECTED), len(fraud)),
            "fraud_pending_external_confirmation": pending_fraud,
            "fraud_pending_rate": _rate(pending_fraud, len(fraud)),
            "borderline_pending_external_confirmation": state(border, S.ELIGIBLE_PENDING_CONFIRMATION),
            "sensitivity_expected_fraud_activations_if_confirmation_misses": {
                f"{int(q * 100)}%": round(pending_fraud * q, 2) for q in MISS_RATES},
            "note": "Pending fraud is held behind external confirmation, not detected. Its eventual outcome depends "
                    "on confirmation quality, which this offline evaluation does not measure.",
        },
        "administrative_workload": {
            "cases": n,
            "manual_reviews": counts.get(S.FLAG_FOR_REVIEW.value, 0),
            "information_requests": counts.get(S.NEEDS_MORE_INFORMATION.value, 0),
            "verification_errors_to_retry": counts.get(S.VERIFICATION_ERROR.value, 0),
            "campaigns_pending_confirmation": counts.get(S.ELIGIBLE_PENDING_CONFIRMATION.value, 0),
            "external_confirmations_required": sum(r["confirmations_required"] for r in rows),
            "per_100_campaigns": {
                "manual_reviews": round(100 * counts.get(S.FLAG_FOR_REVIEW.value, 0) / n, 1) if n else None,
                "information_requests": round(100 * counts.get(S.NEEDS_MORE_INFORMATION.value, 0) / n, 1) if n else None,
                "external_confirmations": round(100 * sum(r["confirmations_required"] for r in rows) / n, 1) if n else None,
            },
            "legitimate_friction": {
                "pending_confirmation_unavoidable": state(legit, S.ELIGIBLE_PENDING_CONFIRMATION),
                "information_request_or_review_avoidable": state(legit, S.NEEDS_MORE_INFORMATION)
                + state(legit, S.FLAG_FOR_REVIEW) + state(legit, S.VERIFICATION_ERROR),
            },
        },
    }
