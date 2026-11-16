"""Metrics for the external-confirmation step, computed from an attempt log.

The same functions consume (a) simulated logs from simulate_external_confirmation.py and
(b) real logs recorded by verifiers in a confirmation pilot (confirmation_log_template.csv).

Attempt-log fields
  campaign_id, label (if known), check, attempt, contact_source (as recorded by the verifier),
  contact_origin (independent | campaign_printed | campaign_out_of_band - real pilots record what the
  verifier knows), outcome, counted (did the workflow accept it towards activation), false_contact_detail
  (campaign-supplied contact differs from the independent one), hours_elapsed, minutes_spent
Campaign-outcome fields
  campaign_id, label, final_state, hours_to_activation, hours_to_flag
"""
import math
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Optional


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def _summary(values: List[float]) -> Optional[dict]:
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(values), "mean": round(statistics.mean(values), 2), "median": round(statistics.median(values), 2),
            "p90": round(ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)], 2)}


def confirmation_metrics(attempts: List[dict], campaigns: List[dict]) -> Dict:
    by_label = defaultdict(list)
    for campaign in campaigns:
        by_label[campaign.get("label") or "unknown"].append(campaign)
    fraud = by_label.get("fraudulent", [])
    legit = by_label.get("legitimate", [])
    independent = [a for a in attempts if a["contact_origin"] == "independent"]
    successful_independent = [a for a in independent if a["outcome"] == "CONFIRMED" and a["counted"]]
    unsuccessful = [a for a in attempts if a["outcome"] in ("UNREACHABLE", "INCONCLUSIVE")]
    campaign_supplied_used = [a for a in attempts if a["contact_origin"] != "independent"]
    false_detail_campaigns = {a["campaign_id"] for a in attempts if a.get("false_contact_detail")}
    n = len(campaigns)
    states = Counter(c["final_state"] for c in campaigns)
    minutes = defaultdict(float)
    attempts_per = Counter()
    for attempt in attempts:
        minutes[attempt["campaign_id"]] += attempt["minutes_spent"]
        attempts_per[attempt["campaign_id"]] += 1
    return {
        "campaigns_entering_confirmation": n,
        "final_states": dict(states),
        "successful_independent_confirmations": {
            "count": len(successful_independent), "per_independent_attempt": _rate(len(successful_independent), len(independent)),
            "by_check": dict(Counter(a["check"] for a in successful_independent)),
        },
        "false_institution_contact_details": {
            "campaigns_with_false_contact_detail": len(false_detail_campaigns),
            "by_label": dict(Counter(c.get("label") for c in campaigns if c["campaign_id"] in false_detail_campaigns)),
            "campaign_supplied_contacts_used_by_verifiers": len(campaign_supplied_used),
            "of_which_accepted_towards_activation": sum(a["counted"] for a in campaign_supplied_used),
            # The workflow re-labels a contact that appears in the uploads as CAMPAIGN_SUPPLIED.
            "of_which_caught_by_upload_contact_matching": sum(a["contact_origin"] == "campaign_printed"
                                                              and a["contact_source"] == "CAMPAIGN_SUPPLIED"
                                                              for a in campaign_supplied_used),
            "of_which_mislabelled_and_undetectable": sum(a["contact_source"] != "CAMPAIGN_SUPPLIED"
                                                         for a in campaign_supplied_used),
        },
        "unsuccessful_verification_attempts": {
            "count": len(unsuccessful), "per_attempt": _rate(len(unsuccessful), len(attempts)),
            "by_outcome": dict(Counter(a["outcome"] for a in unsuccessful)),
            "campaigns_still_pending_at_horizon": states.get("ELIGIBLE_PENDING_CONFIRMATION", 0),
        },
        "confirmation_time_hours": {
            "to_activation_legitimate": _summary([c["hours_to_activation"] for c in legit
                                                  if c.get("hours_to_activation") is not None]),
            "to_activation_all": _summary([c["hours_to_activation"] for c in campaigns
                                           if c.get("hours_to_activation") is not None]),
            "to_flag_fraudulent": _summary([c["hours_to_flag"] for c in fraud if c.get("hours_to_flag") is not None]),
        },
        "administrative_workload": {
            "attempts_total": len(attempts), "attempts_per_campaign": _rate(len(attempts), n),
            "verifier_minutes_total": round(sum(minutes.values()), 1),
            "verifier_minutes_per_campaign": _rate(sum(minutes.values()), n),
            "reviews_triggered_by_confirmation": states.get("FLAG_FOR_REVIEW", 0),
            "attempts_per_campaign_distribution": _summary(list(attempts_per.values())),
        },
        "fraud_prevention": {
            "fraudulent_campaigns_entering_confirmation": len(fraud),
            "prevented_from_activation": sum(c["final_state"] != "VERIFIED_ACTIVE" for c in fraud),
            "prevention_rate": _rate(sum(c["final_state"] != "VERIFIED_ACTIVE" for c in fraud), len(fraud)),
            "activated": sum(c["final_state"] == "VERIFIED_ACTIVE" for c in fraud),
            "flagged_by_contradiction": sum(c["final_state"] == "FLAG_FOR_REVIEW" for c in fraud),
            "still_pending": sum(c["final_state"] == "ELIGIBLE_PENDING_CONFIRMATION" for c in fraud),
        },
        "legitimate_outcomes": {
            "entering_confirmation": len(legit),
            "activated": sum(c["final_state"] == "VERIFIED_ACTIVE" for c in legit),
            "activation_rate": _rate(sum(c["final_state"] == "VERIFIED_ACTIVE" for c in legit), len(legit)),
            "wrongly_flagged": sum(c["final_state"] == "FLAG_FOR_REVIEW" for c in legit),
            "still_pending": sum(c["final_state"] == "ELIGIBLE_PENDING_CONFIRMATION" for c in legit),
        },
    }
