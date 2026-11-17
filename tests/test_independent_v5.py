"""Offline tests of the v5 independent-evaluation tooling.  Engineering fixtures only; no network; no API call."""
import ast
import asyncio
import copy
import csv
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from independent_v5 import (config, datecheck, exclusion, kit, labels, participants, retrieval, runner,  # noqa: E402
                            scorer, stats, validator)
from independent_v5.transport import AuditedTransport, NotSent, PolicyState, StopPolicy  # noqa: E402

FIX = config.FIXTURES
PREREG = config.load_prereg()
SCRIPT = json.loads((FIX / "gemini_script.json").read_text())


def fixture_cases():
    return config.read_jsonl(FIX / "submission.jsonl")


def write_cases(path: Path, cases) -> Path:
    path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    return path


def validate(path, **kwargs):
    kwargs.setdefault("participants", FIX / "participants.csv")
    return validator.validate_submission(path, "engineering", **kwargs)


class Clock:
    def __init__(self, start=datetime(2027, 3, 1, 10, 0, tzinfo=timezone.utc)):
        self.now = start

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any real HTTP helper call fails the test."""
    async def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")
    import app.services.gemini_api as gemini_api
    import app.services.rag as rag
    monkeypatch.setattr(gemini_api, "post_json", forbidden)
    monkeypatch.setattr(rag, "post_json", forbidden)


# ------------------------------------------------------------------ statistics
def test_wilson_matches_the_existing_implementation():
    from group_uncertainty import wilson as existing
    for s, n in [(0, 10), (3, 10), (54, 90), (7, 135)]:
        assert list(stats.wilson(s, n)) == existing(s, n)


def test_mcnemar_exact_and_holm():
    assert stats.mcnemar_exact(0, 5) == 0.0625
    assert stats.mcnemar_exact(1, 9) == pytest.approx(0.021484, abs=1e-6)
    assert stats.mcnemar_exact(0, 0) == 1.0
    assert stats.holm({"a": 0.01, "b": 0.04, "c": 0.03}) == {"a": 0.03, "b": 0.06, "c": 0.06}


def test_reference_values_for_interval_and_test_calculations():
    assert stats.wilson(0, 10) == (0.0, 0.2775) and stats.wilson(3, 10) == (0.1078, 0.6032)
    # one-way ANOVA ICC, hand-computed: groups [1,1],[0,0],[1,0]: grand mean 0.5, SSB = 1, MSB = 0.5,
    # SSW = 0.5, MSW = 1/6, n0 = 2, ICC = (0.5 - 1/6) / (0.5 + 1/6) = 0.5
    assert stats.icc_anova([[1, 1], [0, 0], [1, 0]]) == pytest.approx(0.5)
    assert stats.cluster_size([[1], [1, 0], [1, 0, 1]]) == pytest.approx((1 + 4 + 9) / 6)
    assert stats.zero_event_upper(90) == 0.0327 and stats.zero_event_upper(100) == pytest.approx(0.0295, abs=1e-4)
    # with one case per group the cluster sign-flip test is exactly the exact McNemar test
    for b, c in ((0, 5), (1, 9), (3, 4), (12, 3)):
        assert stats.cluster_sign_flip_test([1] * b + [-1] * c) == pytest.approx(stats.mcnemar_exact(b, c), abs=1e-9)
    # clustered: d = (+2, +2, -1) -> 8 equally likely sign patterns, |T| >= 3 in 4 of them
    assert stats.cluster_sign_flip_test([2, 2, -1]) == 0.5


def test_design_effect_uses_kish_cluster_size_and_icc_floor():
    outcome = stats.clustered_proportion({"a": [1, 0, 1], "b": [0], "c": [1, 1, 0], "d": [0, 0, 1]}, "kish", 0.1)
    assert outcome["cluster_size_kish"] == pytest.approx((9 + 1 + 9 + 9) / 10, abs=1e-4)
    assert outcome["icc_used"] >= 0.1
    assert outcome["effective_n"] == pytest.approx(10 / outcome["design_effect"], abs=0.01)


def test_statistical_validation_record_supports_the_chosen_methods():
    record = json.loads((config.KIT / "statistical_validation.json").read_text())
    summary = record["coverage_summary"]
    assert summary["A|deff_kish_floor_0.1"]["min"] >= 0.94 and summary["A|naive_wilson"]["min"] < 0.9
    assert all(r["type1_cluster_sign_flip"] <= 0.05 for r in record["paired_type1"])
    assert max(r["type1_exact_mcnemar_ignoring_groups"] for r in record["paired_type1"]) > 0.05


def test_clustered_interval_is_conservative_when_icc_cannot_be_estimated():
    outcome = stats.clustered_proportion({f"g{i}": [0, 0, 0] for i in range(10)})
    assert outcome["icc_used"] == 1.0 and outcome["effective_n"] == 10
    assert outcome["ci"] == stats.wilson(0, 10)


def test_design_budget_and_elapsed_days():
    full = stats.design_row("A", {"L": 90, "I": 45, "F": 90, "B": 45}, 2.0, 20, 0.10, 8)
    single = stats.design_row("B", {"L": 90, "I": 45, "F": 90, "B": 45}, 1.0, 20, 0.10, 8)
    assert (full["cases"], full["generation_requests_max"], full["free_tier_days_min"]) == (540, 602, 31)
    assert (single["cases"], single["generation_requests_max"], single["free_tier_days_min"]) == (270, 305, 16)
    assert full["embedding_requests"] == 0 and "simulated" in full["paired_power"]


# ------------------------------------------------------------------ exclusion and duplicates
def test_every_previously_used_corpus_is_registered():
    registry = json.loads(config.EXCLUSION_REGISTRY.read_text())
    stories = set()
    for path in (ROOT / "evaluation").rglob("*.jsonl"):
        rel = str(path.relative_to(ROOT))
        if "/runs/independent_v5" in rel:
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(case, dict) and isinstance(case.get("input"), dict) and case["input"].get("story"):
                stories.add(rel)
                break
    assert stories <= set(registry["sources"]), stories - set(registry["sources"])
    for required in ("evaluation/final_test_scenarios_v3.jsonl", "evaluation/fundraising_scenarios.jsonl",
                     "evaluation/independent_test_150.jsonl", "evaluation/independent_benchmark_100.jsonl",
                     "evaluation/date_aware_dev_eval/scenarios.json", "tests/test_hybrid_v3.py"):
        assert required in registry["sources"]
    items, problems, _, _ = exclusion.load_prior()
    assert problems == []
    assert len(items) >= registry["total_items"] - 50


def _with_story(case_id: str, story: str, tmp_path: Path) -> Path:
    cases = fixture_cases()
    for case in cases:
        if case["case_id"] == case_id:
            case["input"]["story"] = story
    return write_cases(tmp_path / "submission.jsonl", cases)


def test_a_benchmark_case_cannot_enter_even_with_changed_numbers(tmp_path):
    benchmark = config.read_jsonl(ROOT / "evaluation/final_test_scenarios_v3.jsonl")[7]["input"]["story"]
    altered = benchmark
    for digit, other in zip("0123456789", "9876543210"):
        altered = altered.replace(digit, other)
    result = validate(_with_story("ENG-MED-0002-A", altered, tmp_path))
    assert not result["valid"]
    assert any("final_test_scenarios_v3.jsonl" in e for e in result["errors"])


def test_date_aware_templates_and_test_fixture_texts_cannot_enter(tmp_path):
    template = json.loads((ROOT / "evaluation/date_aware_dev_eval/scenarios.json").read_text())["scenarios"][4]["input"]["story"]
    index = exclusion.DuplicateIndex(PREREG["duplicates"]).add_all(exclusion.load_prior()[0])
    assert any(m.other["source"].endswith("scenarios.json") or "date_aware" in m.other["source"]
               for m in index.query(exclusion._PLACEHOLDER.sub("12 March 2027", template), "story"))
    literal = max((n.value for n in ast.walk(ast.parse((ROOT / "tests/test_hybrid_v3.py").read_text()))
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)), key=len)
    assert any(m.other["source"] == "tests/test_hybrid_v3.py" for m in index.query(literal, "document:x"))


def test_near_duplicate_across_scenario_groups_is_rejected(tmp_path):
    cases = fixture_cases()
    copy_case = copy.deepcopy(next(c for c in cases if c["case_id"] == "ENG-EDU-0001-A"))
    copy_case["scenario_group"], copy_case["case_id"] = "ENG-EDU-0099", "ENG-EDU-0099-A"
    copy_case["input"]["story"] = copy_case["input"]["story"].replace("Meghna Das", "Ritika Sen")
    result = validate(write_cases(tmp_path / "s.jsonl", cases + [copy_case]))
    assert any("duplicates scenario group ENG-EDU-0001" in e for e in result["errors"])


def test_near_copies_inside_a_group_are_rejected(tmp_path):
    cases = fixture_cases()
    b = next(c for c in cases if c["case_id"] == "ENG-MED-0001-B")
    b["input"]["story"] = next(c for c in cases if c["case_id"] == "ENG-MED-0001-A")["input"]["story"] + " Thank you."
    result = validate(write_cases(tmp_path / "s.jsonl", cases))
    assert any("near-copies" in e for e in result["errors"])


def test_pilot_cases_cannot_reappear_in_the_test_set(tmp_path):
    pilot = config.read_jsonl(FIX / "pilot.jsonl")
    story = pilot[0]["input"]["story"] + " The family thanks every donor."
    result = validate(_with_story("ENG-MED-0002-A", story, tmp_path), pilot=FIX / "pilot.jsonl")
    assert any("pilot" in e or "ENG-PIL" in e for e in result["errors"])


# ------------------------------------------------------------------ validator
def test_engineering_fixtures_validate_and_are_refused_as_independent_data():
    assert validate(FIX / "submission.jsonl", pilot=FIX / "pilot.jsonl")["valid"]
    assert validator.validate_submission(FIX / "pilot.jsonl", "engineering", FIX / "participants.csv", is_pilot=True)["valid"]
    full = validator.validate_submission(FIX / "submission.jsonl", "full", FIX / "participants.csv")
    assert not full["valid"]
    assert any("must start with 'T5-'" in e for e in full["errors"])


def test_participant_independence_is_enforced(tmp_path):
    rows = list(csv.DictReader((FIX / "participants.csv").open()))
    rows[0]["involved_in_implementation"] = "yes"
    rows.append({**rows[1], "participant_id": "DEVELOPER", "role": "labeller"})
    path = tmp_path / "participants.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=participants.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    result = validate(FIX / "submission.jsonl", participants=path)
    assert any("involved_in_implementation" in e for e in result["errors"])
    registry = participants.load(path)["participants"]
    assert participants.eligible(registry["DEVELOPER"], "labeller")
    assert participants.eligible(None, "author") == ["not in the participant registry"]


def test_keyword_free_cases_are_checked_against_the_lexicons(tmp_path):
    cases = fixture_cases()
    case = next(c for c in cases if c["case_id"] == "ENG-MED-0004-A")
    case["input"]["story"] += " Please send money directly to my personal account."
    result = validate(write_cases(tmp_path / "s.jsonl", cases))
    assert any("keyword_free case contains" in e for e in result["errors"])


def test_dates_are_validated_independently_of_the_system(tmp_path):
    cases = fixture_cases()
    case = next(c for c in cases if c["case_id"] == "ENG-EDU-0001-A")
    case["date_facts"][1]["date"] = "2027-03-30"
    other = next(c for c in cases if c["case_id"] == "ENG-MED-0001-A")
    other["date_facts"][0]["date"] = "2027-03-14"
    other["input"]["documents"][0]["content"] = other["input"]["documents"][0]["content"].replace("14/02/2027", "14/03/2027")
    other["date_facts"][0]["as_written"] = "14/03/2027"
    errors = validate(write_cases(tmp_path / "s.jsonl", cases))["errors"]
    assert any("reads as 2027-03-31, not the declared 2027-03-30" in e for e in errors)
    assert any("issue date after the submission date" in e for e in errors)
    assert datecheck.parse("31/03/2027") == date(2027, 3, 31) and datecheck.parse("5 Jan 2027") == date(2027, 1, 5)
    tree = ast.parse(Path(datecheck.__file__).read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
               {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and m.startswith("app") for m in imported)


def test_fraud_cases_declare_intended_detectability_and_quotas_apply():
    cases = fixture_cases()
    del next(c for c in cases if c["case_id"] == "ENG-MED-0003-A")["intended_detectable_from_dossier"]
    errors = validator.case_errors(next(c for c in cases if c["case_id"] == "ENG-MED-0003-A"), PREREG, "ENG-")
    assert any("intended_detectable_from_dossier" in e for e in errors)
    groups = {}
    for case in fixture_cases():
        groups.setdefault(case["scenario_group"], []).append(case)
    quota_errors = validator._quota_errors(fixture_cases(), groups, PREREG, "full")
    assert any("subtype genuine_but_informal (minimum 5)" in e for e in quota_errors)
    assert any("intended to be detectable" in e or "fraud groups" in e for e in quota_errors)


def test_external_environment_needs_the_cost_issuer(tmp_path):
    cases = fixture_cases()
    del cases[0]["external_environment"]["COST_ISSUER"]
    errors = validate(write_cases(tmp_path / "s.jsonl", cases))["errors"]
    assert any("COST_ISSUER" in e for e in errors)


def test_labellers_copy_hides_author_intent(tmp_path):
    out = tmp_path / "blind.jsonl"
    validator.blind_copy(FIX / "submission.jsonl", out)
    for case in config.read_jsonl(out):
        assert not set(validator.HIDDEN_FROM_LABELLERS) & set(case)
        assert "external_environment" in case and "input" in case


def test_recruitment_feasibility_check(tmp_path):
    staffing = PREREG["staffing"]
    assert participants.feasibility(participants.load(FIX / "participants.csv"), staffing)["designs"]["A"]["feasible"] is False
    rows = [("P-A1", "author", 130), ("P-A2", "author", 130), ("P-A3", "author", 130), ("P-L1", "labeller", 90),
            ("P-L2", "labeller", 90), ("P-J1", "adjudicator", 25), ("P-C1", "coordinator", 35)]
    path = tmp_path / "registry.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=participants.FIELDS + ["committed_hours"])
        writer.writeheader()
        for pid, role, hours in rows:
            writer.writerow({"participant_id": pid, "role": role, "independence_declared": "yes",
                             "involved_in_implementation": "no", "involved_in_prior_benchmarks_or_tuning": "no",
                             "saw_verifier_code_or_lexicons": "no", "saw_prior_corpora": "no",
                             "declared_on": "2027-01-01", "committed_hours": hours, "notes": ""})
    result = participants.feasibility(participants.load(path), staffing)
    assert result["designs"]["A"]["feasible"] and result["designs"]["B"]["feasible"]
    rows[0] = ("P-A1", "author", 10)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=participants.FIELDS + ["committed_hours"])
        writer.writeheader()
        for pid, role, hours in rows:
            writer.writerow({"participant_id": pid, "role": role, "independence_declared": "yes",
                             "involved_in_implementation": "no", "involved_in_prior_benchmarks_or_tuning": "no",
                             "saw_verifier_code_or_lexicons": "no", "saw_prior_corpora": "no",
                             "declared_on": "2027-01-01", "committed_hours": hours, "notes": ""})
    result = participants.feasibility(participants.load(path), staffing)
    assert not result["designs"]["A"]["feasible"] and result["designs"]["B"]["feasible"]


# ------------------------------------------------------------------ labels
def test_label_agreement_adjudication_and_seal(tmp_path):
    report = labels.agreement(FIX / "labels_a.csv", FIX / "labels_b.csv")
    assert report["cases_with_disagreement"] == ["ENG-COM-0005-A", "ENG-MED-0005-A"]
    registry = participants.load(FIX / "participants.csv")["participants"]
    merged = labels.merge(FIX / "labels_a.csv", FIX / "labels_b.csv", FIX / "adjudication.csv", tmp_path / "final.csv", registry)
    assert merged["status"] == {"agreed": 16, "adjudicated": 2}
    final = labels.read_final(tmp_path / "final.csv")
    assert final["ENG-MED-0005-A"]["truth_label"] == "borderline"
    assert final["ENG-COM-0005-A"]["documentation"] == "complete" and final["ENG-COM-0005-A"]["missing_items"] == ""
    seal = labels.seal(tmp_path / "final.csv", tmp_path / "seal.json", report)
    assert seal["sha256"] == config.sha256_file(tmp_path / "final.csv")
    with pytest.raises(SystemExit):
        labels.seal(tmp_path / "final.csv", tmp_path / "seal.json", report)


def test_unadjudicated_truth_disagreement_becomes_borderline(tmp_path):
    labels.merge(FIX / "labels_a.csv", FIX / "labels_b.csv", None, tmp_path / "final.csv")
    final = labels.read_final(tmp_path / "final.csv")
    assert final["ENG-MED-0005-A"]["adjudication_status"] == "unresolved"
    assert final["ENG-MED-0005-A"]["truth_label"] == "borderline"


def test_label_sheet_rules(tmp_path):
    rows = list(csv.DictReader((FIX / "labels_a.csv").open()))
    rows[2]["acceptable_end_states"] = "APPROVED"          # an incomplete case
    path = tmp_path / "sheet.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=labels.SHEET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    ids = [c["case_id"] for c in fixture_cases()]
    result = labels.check_sheet(path, ids, participants.load(FIX / "participants.csv")["participants"], {"ENG-L01"})
    assert any("APPROVED is acceptable only" in e for e in result["errors"])
    assert any("also authored" in e for e in result["errors"])


def test_adjudicator_cannot_be_one_of_the_labellers(tmp_path):
    rows = list(csv.DictReader((FIX / "adjudication.csv").open()))
    for row in rows:
        row["adjudicator_id"] = "ENG-L01"
    path = tmp_path / "adj.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=labels.ADJUDICATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(SystemExit, match="must not be one of the two labellers"):
        labels.merge(FIX / "labels_a.csv", FIX / "labels_b.csv", path, tmp_path / "final.csv")


# ------------------------------------------------------------------ retrieval
def test_retrieval_reproduces_production_fallback_without_network(monkeypatch):
    from app.config import settings
    from app.services import rag
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "a-configured-key-must-not-be-used")
    saved = (rag.UPLOAD_DIR, rag.settings, rag.post_json)
    case = next(c for c in fixture_cases() if c["case_id"] == "ENG-MED-0001-A")
    chunks, coverage = asyncio.run(retrieval.retrieve(case["input"]))
    assert (rag.UPLOAD_DIR, rag.settings, rag.post_json) == saved
    query = retrieval.production_query(case["input"])
    expected = []
    for document in case["input"]["documents"]:
        for chunk in rag.chunk_document(document["content"], {"title": document["title"], "doc_type": document["doc_type"]}):
            chunk["relevance"] = round(rag._lexical_score(query, chunk["text"]), 4)
            expected.append(chunk)
    expected = [c for c in sorted(expected, key=lambda c: c["relevance"], reverse=True) if c["relevance"] > 0][:5]
    assert [(c["title"], c["text"], c["relevance"]) for c in chunks] == [(c["title"], c["text"], c["relevance"]) for c in expected]
    assert coverage["total_chunks"] == 11 and coverage["retrieved"] == 5 and not coverage["all_chunks_retrieved"]
    assert coverage["embedding_requests"] == 0
    assert "Salem, Tamil Nadu IN" in query and "2,40,000" in query


# ------------------------------------------------------------------ transport and stopping rules
def test_transport_refuses_other_models_and_the_cap_without_sending(tmp_path):
    sent = []

    async def post(*args, **kwargs):
        sent.append(1)
        return {"candidates": []}
    transport = AuditedTransport(post, tmp_path / "requests.jsonl", cap=1, model_id="gemini-3.6-flash", clock=Clock())
    url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
    with pytest.raises(NotSent):
        asyncio.run(transport(url.format("gemini-3.8-flash"), "secret-key-value-123", {}, "generation", 10))
    asyncio.run(transport(url.format("gemini-3.6-flash"), "secret-key-value-123", {}, "generation", 10))
    with pytest.raises(NotSent):
        asyncio.run(transport(url.format("gemini-3.6-flash"), "secret-key-value-123", {}, "generation", 10))
    assert len(sent) == 1 and transport.sent() == 1
    row = transport.rows()[0]
    assert set(row) >= {"model", "status", "http_seconds", "model_version", "prompt_tokens"} and "secret-key-value-123" not in json.dumps(row)


def _policy(cap=1000, allowance=100, start=None):
    start = start or datetime(2027, 3, 1, 10, 0, tzinfo=timezone.utc)
    return StopPolicy(PREREG["stopping_rules"], cap, allowance, PolicyState(started_at=start.isoformat())), start


def test_stopping_rules():
    policy, now = _policy()
    assert policy.after_request(now, ["AUTHENTICATION"], 1).reason == "CONFIGURATION_ERROR:AUTHENTICATION"
    policy, now = _policy()
    quota = policy.after_request(now, ["QUOTA_EXHAUSTED"], 0)
    assert quota.kind == "PAUSE" and quota.resume_not_before.startswith("2027-03-02T08:00")
    policy, now = _policy()
    assert policy.after_request(now, ["SERVER_ERROR"], 1).kind == "RETRY"
    assert policy.after_request(now, ["SERVER_ERROR"], 2).reason == "RETRY_ALREADY_USED"
    paused = policy.after_request(now, ["SERVER_ERROR"] * 3, 1)
    assert paused.kind == "PAUSE" and paused.reason == "CONSECUTIVE_TRANSIENT_FAILURES"
    assert policy.before_request(now + timedelta(minutes=30), 3).kind == "PAUSE"
    assert policy.before_request(now + timedelta(minutes=61), 3).kind == "CONTINUE"
    policy.after_request(now, ["SERVER_ERROR"] * 3, 1)
    third = policy.after_request(now, ["SERVER_ERROR"] * 3, 1)
    assert third.reason.endswith("_DAILY_LIMIT") and third.resume_not_before.startswith("2027-03-02T00:00")
    policy, now = _policy()
    history = ([None] * 3 + ["SERVER_ERROR"]) * 25 + ["SERVER_ERROR"] * 9
    assert policy.after_request(now, history[:100] + [None], 1).kind == "CONTINUE"
    assert policy.after_request(now, history, 1).reason == "TRANSIENT_FAILURE_RATE_EXCEEDED"
    policy, now = _policy(cap=5)
    assert policy.before_request(now, 5).reason == "CALL_LIMIT_REACHED"
    policy, now = _policy()
    assert policy.before_request(now + timedelta(days=45), 0).reason == "CALENDAR_LIMIT_REACHED"
    policy, now = _policy(allowance=0)
    assert policy.claim_retry().reason == "RETRY_ALLOWANCE_USED"


def test_stopping_rules_never_read_outcomes():
    source = Path(StopPolicy.__module__.replace(".", "/") + ".py")
    text = (ROOT / "evaluation" / source).read_text()
    for word in ("truth_label", "ground_truth", "decision\"]", "APPROVED", "labels"):
        assert word not in text.split("class StopPolicy")[1]


# ------------------------------------------------------------------ runner
def _dry(tmp_path, script=SCRIPT, clock=None, resume=False, submission=FIX / "submission.jsonl"):
    return runner.dry_run(submission, tmp_path / "run", script, resume=resume, clock=clock or Clock())


def test_engineering_dry_run_end_to_end(tmp_path):
    state = _dry(tmp_path)
    assert state["status"] == "COMPLETE"
    rd = runner.RunDir(tmp_path / "run")
    outputs = rd.output_rows()
    assert len(outputs) == 18 and len({o["case_id"] for o in outputs}) == 18
    manifest = json.loads(rd.manifest.read_text())
    assert len(runner.RunDir._read(rd.requests)) <= manifest["cap"] == 20
    forbidden = {"author_intended_label", "author_intended_documentation", "mechanism", "truth_label", "labels"}
    for output in outputs:
        assert not forbidden & set(output)
        v3 = output["systems"]["hybrid_v3"]
        assert v3["decision"] != "REJECTED"
        if v3["decision"] == "APPROVED":
            assert v3["confirmation_simulated"]["initial_state"] == "ELIGIBLE_PENDING_CONFIRMATION"
            assert v3["authenticity"] == "UNCONFIRMED"
        assert "SIMULATED" in v3["confirmation_simulated"]["simulation"]
    rejected = next(o for o in outputs if o["case_id"] == "ENG-COM-0004-A")
    assert rejected["gemini"]["decision"] == "REJECTED" and rejected["systems"]["hybrid_v3"]["decision"] == "FLAG_FOR_REVIEW"
    timeouts = next(o for o in outputs if o["case_id"] == "ENG-EDU-0005-A")
    assert timeouts["gemini_requests"] == 2 and timeouts["systems"]["hybrid_v3"]["decision"] == "VERIFICATION_ERROR"
    assert runner.status(tmp_path / "run")["cases_completed"] == 18


def test_dry_run_refuses_the_independent_test_set(tmp_path):
    cases = fixture_cases()
    for case in cases:
        case["case_id"] = "T5-" + case["case_id"][4:]
    path = write_cases(tmp_path / "t5.jsonl", cases)
    with pytest.raises(SystemExit, match="accepts only engineering fixtures"):
        runner.dry_run(path, tmp_path / "run", SCRIPT)


def test_quota_pause_and_resume_without_repeating_cases(tmp_path):
    script = {cid: ["approve"] for cid in SCRIPT}
    script["ENG-MED-0003-A"] = ["QUOTA_EXHAUSTED", "flag_grounded"]
    clock = Clock()
    first = _dry(tmp_path, script, clock)
    assert first["status"] == "PAUSED" and first["reason"] == "QUOTA_EXHAUSTED"
    done_before = len(runner.RunDir(tmp_path / "run").output_rows())
    sent_before = runner.status(tmp_path / "run")["requests_sent"]
    clock.now += timedelta(hours=1)
    early = _dry(tmp_path, script, clock, resume=True)
    assert early["status"] == "PAUSED" and runner.status(tmp_path / "run")["requests_sent"] == sent_before
    clock.now = datetime(2027, 3, 2, 8, 1, tzinfo=timezone.utc)
    final = _dry(tmp_path, script, clock, resume=True)
    assert final["status"] == "COMPLETE"
    outputs = runner.RunDir(tmp_path / "run").output_rows()
    assert len(outputs) == 18 and len({o["case_id"] for o in outputs}) == 18 and done_before < 18


def test_configuration_error_stops_for_good(tmp_path):
    order = runner.ordered(fixture_cases(), PREREG["analysis"]["order_seed"])
    script = {cid: ["approve"] for cid in SCRIPT}
    script[order[0]["case_id"]] = ["AUTHENTICATION"]
    assert _dry(tmp_path, script)["status"] == "STOPPED"
    again = _dry(tmp_path, script, resume=True)
    assert again["status"] == "STOPPED" and runner.status(tmp_path / "run")["requests_sent"] == 1


def test_run_directory_is_never_reused(tmp_path):
    _dry(tmp_path)
    with pytest.raises(SystemExit, match="never reused"):
        _dry(tmp_path)


def test_live_execution_refuses_without_every_precondition(tmp_path, monkeypatch):
    monkeypatch.delenv(config.APPROVAL_ENV, raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    garbage = tmp_path / "labels.csv"
    garbage.write_text("this is not a CSV the runner should ever parse\x00", encoding="utf-8")
    label_seal = tmp_path / "label_seal.json"
    label_seal.write_text(json.dumps({"sha256": config.sha256_file(garbage)}))
    result = runner.live_preconditions(FIX / "submission.jsonl", tmp_path / "missing_seal.json", PREREG, "main",
                                       None, garbage, label_seal)
    problems = " | ".join(result["problems"])
    for expected in ("not APPROVED", "not sealed", "no written API authorisation", config.APPROVAL_ENV,
                     "no substitution", "no API key"):
        assert expected in problems
    assert "labels are not sealed" not in problems            # only the hash was checked, the content never parsed
    with pytest.raises(SystemExit, match="Refusing to make any API call"):
        runner.execute(FIX / "submission.jsonl", tmp_path / "missing_seal.json", tmp_path / "run", "main",
                       tmp_path / "auth.json", garbage, label_seal)
    assert not (tmp_path / "run").exists()


def test_authorisation_must_match_the_plan(tmp_path):
    auth = {"scope": "main", "model": "gemini-3.8-flash", "max_generation_requests": 999, "max_embedding_requests": 0,
            "paid_usage": True, "submission_sha256": "x", "authorized_by": "owner", "authorized_at": "2027-01-01"}
    path = tmp_path / "auth.json"
    path.write_text(json.dumps(auth))
    problems = runner.check_authorisation(path, PREREG, FIX / "submission.jsonl", "main", 20)
    joined = " | ".join(problems)
    assert "model" in joined and "paid_usage" in joined and "submission_sha256" in joined and "no larger than the plan" in joined


def test_plan_is_offline_and_reports_designs():
    result = runner.plan()
    assert result["api_calls_made"] == 0 and result["embedding_requests"] == 0 and result["paid_usage_allowed"] is False
    designs = {d["design"]: d for d in result["designs"]}
    assert designs["A_full_270_groups_2_cases"]["generation_requests_max"] == 602
    assert designs["B_full_270_groups_1_case"]["generation_requests_max"] == 305
    assert designs["D_minimal_90_groups_1_case"]["free_tier_days_min"] == 6


# ------------------------------------------------------------------ scorer
def _scored(tmp_path):
    _dry(tmp_path)
    report = labels.agreement(FIX / "labels_a.csv", FIX / "labels_b.csv")
    labels.merge(FIX / "labels_a.csv", FIX / "labels_b.csv", FIX / "adjudication.csv", tmp_path / "final.csv")
    labels.seal(tmp_path / "final.csv", tmp_path / "seal.json", report)
    return scorer.score(tmp_path / "run", tmp_path / "final.csv", tmp_path / "seal.json", FIX / "submission.jsonl",
                        tmp_path / "scores")


def test_scorer_end_to_end_on_engineering_fixtures(tmp_path):
    result = _scored(tmp_path)
    assert result["complete_run"] and result["cases_scored"] == 18
    criteria = result["criteria_hybrid_v3"]
    assert criteria["all_gates_pass"] is True
    assert criteria["verdict"] in {"MEETS_MINIMUM_STANDARD", "DOES_NOT_MEET_MINIMUM_STANDARD", "INCONCLUSIVE"}
    assert set(criteria["primary_endpoint"]) == {"H1_dossier_detectable_fraud_recall_minimum"}
    assert set(criteria["key_secondary"]) == {"K1_false_positive_rate", "K2_legitimate_complete_approval"}
    if criteria["primary_endpoint"]["H1_dossier_detectable_fraud_recall_minimum"]["result"] != "MET":
        assert criteria["research_target"]["R1_dossier_detectable_fraud_recall_target"]["result"] == "NOT_ASSESSED"
    for gate in criteria["gates"].values():
        assert gate["count"] > 0 or gate["one_sided_95_upper_if_zero"] > 0     # zero events never mean a zero rate
    funnel = result["metrics_itt"]["hybrid_v3"]["S_stage_funnel"]
    assert all(v["activation_without_final_approval"] == 0 for v in funnel.values())
    assert set(result["comparisons_hybrid_v3_vs_hybrid_v2"]) == set(PREREG["success_criteria"]["comparisons_with_hybrid_v2"]["family"])
    assert result["fairness_noninferiority"]["result"] in {"NON_INFERIOR", "INFERIOR", "INCONCLUSIVE"}
    assert "legitimate_lost_per_fraud_prevented" in result["tradeoff"]["hybrid_v3_vs_hybrid_v2"]
    gbi = result["metrics_itt"]["hybrid_v3"]["F1_genuine_but_informal_outcomes"]
    assert gbi["information_request"]["n"] == 1
    metrics = result["metrics_itt"]["hybrid_v3"]
    approved = sum(n for d in metrics["decisions"].values() for k, n in d.items() if k == "APPROVED")
    activated = result["tradeoff"]["hybrid_v3"]["counts"]["legitimate_activated_simulated"] + \
        result["tradeoff"]["hybrid_v3"]["counts"]["fraud_activated_simulated"]
    assert approved > activated                                  # provisional approval is not activation
    for key in ("comparisons_hybrid_v3_vs_hybrid_v2", "tradeoff", "api", "metrics_complete_case"):
        assert result[key]
    assert {"M10_first_attempt_success", "M11_latency_seconds"} <= set(result["api"])
    assert (tmp_path / "scores" / "report.md").exists() and (tmp_path / "scores" / "case_level.csv").exists()
    with pytest.raises(SystemExit, match="written once"):
        scorer.score(tmp_path / "run", tmp_path / "final.csv", tmp_path / "seal.json", FIX / "submission.jsonl",
                     tmp_path / "scores")


def test_scorer_refuses_changed_labels_and_writing_inside_app(tmp_path):
    _scored(tmp_path)
    with pytest.raises(SystemExit, match="inside app"):
        scorer.score(tmp_path / "run", tmp_path / "final.csv", tmp_path / "seal.json", FIX / "submission.jsonl",
                     ROOT / "app" / "scores_v5")
    (tmp_path / "final.csv").write_text((tmp_path / "final.csv").read_text().replace("borderline", "legitimate", 1))
    with pytest.raises(SystemExit, match="differ from their seal"):
        scorer.score(tmp_path / "run", tmp_path / "final.csv", tmp_path / "seal.json", FIX / "submission.jsonl",
                     tmp_path / "scores2")


def _module_imports(path: Path) -> set:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(("." * node.level) + (node.module or ""))
            if node.level and not node.module:
                names |= {"." + a.name for a in node.names}
    return names


def test_scoring_pipeline_cannot_reach_the_frozen_implementation():
    package = Path(scorer.__file__).parent
    allowed_local = {".config", ".stats", ".labels", ".participants", "."}
    seen, queue = set(), ["scorer"]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        imports = _module_imports(package / f"{name}.py")
        assert not any(i == "app" or i.startswith("app.") for i in imports), (name, imports)
        local = {i for i in imports if i.startswith(".")}
        assert local <= allowed_local | {".config", ".labels", ".stats"} | {"."}, (name, local)
        queue += [i.lstrip(".") for i in local if i.lstrip(".")]
    assert seen == {"scorer", "config", "labels", "stats", "participants"}
    cli = _module_imports(ROOT / "evaluation" / "score_independent_test_v5.py")
    assert not any(i.startswith("app") for i in cli)


def test_judgement_rule():
    assert scorer.judge({"estimate": 0.8, "ci": (0.6, 0.9)}, "lower", 0.5)["result"] == "MET"
    assert scorer.judge({"estimate": 0.8, "ci": (0.4, 0.9)}, "lower", 0.5)["result"] == "INCONCLUSIVE"
    assert scorer.judge({"estimate": 0.4, "ci": (0.2, 0.6)}, "lower", 0.5)["result"] == "NOT_MET"
    assert scorer.judge({"estimate": 0.05, "ci": (0.01, 0.12)}, "upper", 0.10)["result"] == "INCONCLUSIVE"
    assert scorer.judge({"estimate": None}, "upper", 0.10)["result"] == "NOT_ESTIMABLE"


def test_unsafe_activation_types_are_detected():
    base = {"activated": True, "activation_allowed": True, "final_approved": True, "pending_checks": [],
            "documentation": "complete", "truth": "legitimate",
            "satisfied": [{"source": "PLATFORM_KYC", "outcome": "CONFIRMED"}], "confirmation_records": 3,
            "campaign_supplied_satisfied": 0, "activation_triggers": ["confirmation"]}
    assert not any(scorer.unsafe_activation(base).values())
    assert scorer.unsafe_activation({**base, "truth": "fraudulent"})["a"]
    assert scorer.unsafe_activation({**base, "satisfied": [{"source": "CAMPAIGN_SUPPLIED", "outcome": "CONFIRMED"}],
                                     "campaign_supplied_satisfied": 1})["e"]
    assert scorer.unsafe_activation({**base, "activation_triggers": ["reviewer"]})["d"]
    assert scorer.unsafe_activation({**base, "documentation": "incomplete"})["c"]
    assert scorer.unsafe_activation({**base, "final_approved": False})["b"]
    assert not any(scorer.unsafe_activation({**base, "activated": False, "truth": "fraudulent"}).values())


def test_any_fraud_activation_fails_the_zero_tolerance_gate(tmp_path):
    """A fraud case that every independent party confirms (collusive) is activated in the simulation: G2 fails,
    and the decomposition attributes it to fraud no independent party reveals."""
    cases = fixture_cases()
    case = next(c for c in cases if c["case_id"] == "ENG-COM-0003-A")
    for party in ("BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION", "COST_ISSUER"):
        case["external_environment"][party]["independent_response"] = "CONFIRMED"
    case["external_environment"]["COST_ISSUER"].update({"amount_stated_inr": 400000, "other_payers_inr": 0})
    submission = write_cases(tmp_path / "collusive.jsonl", cases)
    runner.dry_run(submission, tmp_path / "run", SCRIPT, clock=Clock())
    report = labels.agreement(FIX / "labels_a.csv", FIX / "labels_b.csv")
    labels.merge(FIX / "labels_a.csv", FIX / "labels_b.csv", FIX / "adjudication.csv", tmp_path / "final.csv")
    labels.seal(tmp_path / "final.csv", tmp_path / "seal.json", report)
    result = scorer.score(tmp_path / "run", tmp_path / "final.csv", tmp_path / "seal.json", submission, tmp_path / "scores")
    gate = result["criteria_hybrid_v3"]["gates"]["G2_no_unsafe_activation"]
    assert gate["result"] == "FAIL" and gate["type_counts"]["a"] == 1
    assert result["criteria_hybrid_v3"]["verdict"] == "DOES_NOT_MEET_MINIMUM_STANDARD"
    decomposition = result["metrics_itt"]["hybrid_v3"]["M8_unsafe_activations"]["type_a_decomposition"]
    assert decomposition["revealed_by_no_independent_party"] == ["ENG-COM-0003-A"]


# ------------------------------------------------------------------ kit and pre-registration
def test_kit_cannot_be_sealed_before_approval():
    assert PREREG["status"] == "PROPOSED"
    with pytest.raises(SystemExit, match="has not been approved"):
        kit.seal()
    assert kit.verify()["valid"] is False
    assert "tests/test_independent_v5.py" in kit.kit_files()


def test_preregistration_fixes_model_retrieval_and_budget():
    assert PREREG["model"]["id"] == "gemini-3.6-flash" and PREREG["model"]["substitution_allowed"] is False
    assert PREREG["api_usage"] == {**PREREG["api_usage"], "paid_usage_allowed": False, "approved_requests": 0,
                                   "quota_verified": False}
    assert PREREG["model"]["availability_verified"] is False
    assert PREREG["retrieval"]["embedding_requests"] == 0 and "not the exact production pipeline" in PREREG["retrieval"]["claim_restriction"]
    assert PREREG["reference_date"]["rule"].startswith("input.submitted_on")
    assert PREREG["stopping_rules"]["never_stop_on_results"] is True
    gates = PREREG["success_criteria"]["gates"]
    assert {"G1_no_provisional_approval_of_incomplete_cases", "G2_no_unsafe_activation", "G3_no_rejection_from_gemini_alone",
            "G4_provisional_approval_never_activation", "G5_no_campaign_supplied_confirmation_accepted"} <= set(gates)
    assert "(a)-(e)" in gates["G2_no_unsafe_activation"] and "cannot establish a zero" in gates["interpretation"]
    primary = PREREG["success_criteria"]["primary_endpoint"]["H1_dossier_detectable_fraud_recall_minimum"]
    assert primary["threshold"] == 0.70 and primary["bound"] == "lower"
    assert PREREG["success_criteria"]["research_target"]["R1_dossier_detectable_fraud_recall_target"]["threshold"] == 0.80
    assert PREREG["analysis"]["cluster_size_rule"] == "kish" and PREREG["analysis"]["icc_floor"] == 0.10
    assert "differs_from_production" in PREREG["retrieval"]
