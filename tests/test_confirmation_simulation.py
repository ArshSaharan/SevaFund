"""Tests for confirmation metrics and the workflow simulation (logic, not real-world numbers)."""
import random
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from app.services.development_approval_workflow import AutomatedOutcome  # noqa: E402
from confirmation_metrics import confirmation_metrics  # noqa: E402
import simulate_external_confirmation as sim  # noqa: E402


def population(labels):
    return [{"campaign_id": f"C{i}", "label": label,
             "outcome": AutomatedOutcome(decision="APPROVED", category="MEDICAL")} for i, label in enumerate(labels)]


def run(labels, assumptions, replications=50):
    per_run, attempts, outcomes = sim.simulate(population(labels), assumptions, replications, seed=7)
    return per_run, attempts, outcomes


def test_honest_independent_channels_never_activate_fraud():
    a = replace(sim.Assumptions(), p_spoofed_directory=0.0, p_insider_collusion=0.0, p_careless_verifier=0.5,
                p_fake_contact_printed=1.0)
    per_run, _, _ = run(["fraudulent"] * 20, a)
    assert all(m["fraud_prevention"]["activated"] == 0 for m in per_run)


def test_printed_campaign_contacts_are_never_accepted_even_when_mislabelled():
    a = replace(sim.Assumptions(), p_careless_verifier=1.0, p_fraud_fake_contact=1.0, p_fake_contact_printed=1.0,
                p_spoofed_directory=0.0, p_insider_collusion=0.0)
    per_run, attempts, _ = run(["fraudulent"] * 20, a)
    used = [x for x in attempts if x["contact_origin"] != "independent"]
    assert used and not any(x["counted"] for x in used)
    assert all(x["contact_source"] == "CAMPAIGN_SUPPLIED" for x in used)
    assert per_run[0]["false_institution_contact_details"]["of_which_caught_by_upload_contact_matching"] == len(used)


def test_out_of_band_mislabelled_contact_is_the_residual_risk():
    a = replace(sim.Assumptions(), p_careless_verifier=1.0, p_fraud_fake_contact=1.0, p_fake_contact_printed=0.0,
                p_fraud_kyc_pass=1.0, p_fraud_payee_lookalike=1.0, p_spoofed_directory=0.0, p_insider_collusion=0.0,
                p_unreachable=0.0)
    per_run, _, _ = run(["fraudulent"] * 10, a, replications=5)
    assert per_run[0]["fraud_prevention"]["activated"] == 10           # documented limitation, now quantified


def test_compromised_channel_plus_passing_kyc_and_payee_activates_fraud():
    a = replace(sim.Assumptions(), p_spoofed_directory=1.0, p_fraud_kyc_pass=1.0, p_fraud_payee_lookalike=1.0,
                p_careless_verifier=0.0, p_unreachable=0.0)
    per_run, _, _ = run(["fraudulent"] * 5, a, replications=3)
    assert per_run[0]["fraud_prevention"]["activated"] == 5


def test_genuine_campaigns_activate_when_contacts_answer():
    a = replace(sim.Assumptions(), p_unreachable=0.0, p_legit_record_mismatch=0.0, p_careless_verifier=0.0)
    per_run, _, outcomes = run(["legitimate"] * 10, a, replications=3)
    assert per_run[0]["legitimate_outcomes"]["activation_rate"] == 1.0
    assert all(o["hours_to_activation"] is not None for o in outcomes)


def test_unreachable_contacts_leave_campaigns_pending_not_flagged():
    a = replace(sim.Assumptions(), p_unreachable=1.0, p_careless_verifier=0.0)
    per_run, _, _ = run(["legitimate"] * 5, a, replications=2)
    m = per_run[0]
    assert m["legitimate_outcomes"]["still_pending"] == 5 and m["legitimate_outcomes"]["wrongly_flagged"] == 0
    assert m["unsuccessful_verification_attempts"]["count"] > 0


def test_simulation_is_reproducible():
    first = run(["legitimate", "fraudulent", "borderline"] * 5, sim.Assumptions(), 10)[0]
    second = run(["legitimate", "fraudulent", "borderline"] * 5, sim.Assumptions(), 10)[0]
    assert first == second


def test_metrics_on_a_hand_written_pilot_log():
    attempts = [
        {"campaign_id": "A", "check": "INSTITUTION", "attempt": 1, "contact_origin": "independent",
         "contact_source": "OFFICIAL_DIRECTORY", "outcome": "UNREACHABLE", "counted": False,
         "false_contact_detail": False, "hours_elapsed": 20, "minutes_spent": 15},
        {"campaign_id": "A", "check": "INSTITUTION", "attempt": 2, "contact_origin": "independent",
         "contact_source": "OFFICIAL_DIRECTORY", "outcome": "CONFIRMED", "counted": True,
         "false_contact_detail": False, "hours_elapsed": 50, "minutes_spent": 15},
        {"campaign_id": "B", "check": "INSTITUTION", "attempt": 0, "contact_origin": "campaign_printed",
         "contact_source": "CAMPAIGN_SUPPLIED", "outcome": "CONFIRMED", "counted": False,
         "false_contact_detail": True, "hours_elapsed": 5, "minutes_spent": 10},
        {"campaign_id": "B", "check": "INSTITUTION", "attempt": 1, "contact_origin": "independent",
         "contact_source": "OFFICIAL_DIRECTORY", "outcome": "CONTRADICTED", "counted": False,
         "false_contact_detail": True, "hours_elapsed": 30, "minutes_spent": 15},
    ]
    campaigns = [{"campaign_id": "A", "label": "legitimate", "final_state": "VERIFIED_ACTIVE",
                  "hours_to_activation": 50, "hours_to_flag": None},
                 {"campaign_id": "B", "label": "fraudulent", "final_state": "FLAG_FOR_REVIEW",
                  "hours_to_activation": None, "hours_to_flag": 30}]
    m = confirmation_metrics(attempts, campaigns)
    assert m["successful_independent_confirmations"]["count"] == 1
    assert m["false_institution_contact_details"]["campaigns_with_false_contact_detail"] == 1
    assert m["false_institution_contact_details"]["of_which_caught_by_upload_contact_matching"] == 1
    assert m["unsuccessful_verification_attempts"]["count"] == 1
    assert m["confirmation_time_hours"]["to_activation_legitimate"]["mean"] == 50
    assert m["fraud_prevention"]["prevention_rate"] == 1.0
    assert m["administrative_workload"]["verifier_minutes_per_campaign"] == 27.5


def test_real_pilot_log_is_replayed_through_the_workflow(tmp_path):
    from analyze_confirmation_log import main as analyze
    campaigns = tmp_path / "campaigns.csv"
    campaigns.write_text(
        "campaign_id,label,category,beneficiary_type,contacts_in_uploads,supplied_contact_matches_directory\n"
        "P1,,MEDICAL,SELF,,\n"
        "P2,fraudulent,EDUCATION,SELF,+91 98450 12345,no\n")
    attempts = tmp_path / "attempts.csv"
    rows = [
        "P1,BENEFICIARY,1,independent,PLATFORM_KYC,kyc,CONFIRMED,2026-12-01T10:00:00+05:30,2026-12-01T10:05:00+05:30,3,V1,",
        "P1,PAYMENT_DESTINATION,1,independent,PLATFORM_KYC,bank,CONFIRMED,2026-12-01T10:10:00+05:30,2026-12-01T10:15:00+05:30,3,V1,",
        "P1,INSTITUTION,1,independent,OFFICIAL_DIRECTORY,+91 80 2222 0000,CONFIRMED,2026-12-02T10:00:00+05:30,2026-12-02T10:20:00+05:30,20,V1,",
        # careless: number printed in the uploads, recorded as directory -> downgraded, never counted
        "P2,INSTITUTION,1,campaign_printed,OFFICIAL_DIRECTORY,+91-98450-12345,CONFIRMED,2026-12-01T11:00:00+05:30,2026-12-01T11:10:00+05:30,10,V2,",
        "P2,INSTITUTION,2,independent,OFFICIAL_DIRECTORY,+91 80 3333 0000,CONTRADICTED,2026-12-02T11:00:00+05:30,2026-12-02T11:15:00+05:30,15,V2,",
    ]
    attempts.write_text("campaign_id,check,attempt,contact_origin,contact_source,contact_reference,outcome,started_at,"
                        "finished_at,minutes_spent,verifier_id,notes\n" + "\n".join(rows) + "\n")
    m = analyze([str(campaigns), str(attempts)])
    assert m["final_states"] == {"VERIFIED_ACTIVE": 1, "FLAG_FOR_REVIEW": 1}
    assert m["false_institution_contact_details"]["of_which_accepted_towards_activation"] == 0
    assert m["false_institution_contact_details"]["of_which_caught_by_upload_contact_matching"] == 1
    assert m["false_institution_contact_details"]["campaigns_with_false_contact_detail"] == 1
    assert m["confirmation_time_hours"]["to_activation_all"]["mean"] == 24.33
    assert m["fraud_prevention"]["prevention_rate"] == 1.0


def test_templates_are_valid_input(tmp_path):
    from analyze_confirmation_log import main as analyze
    m = analyze([str(ROOT / "evaluation/confirmation_pilot/campaigns_template.csv"),
                 str(ROOT / "evaluation/confirmation_pilot/attempts_template.csv")])
    assert m["final_states"] == {"ELIGIBLE_PENDING_CONFIRMATION": 1}
