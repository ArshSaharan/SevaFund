"""The Gemini evaluation framework is prepared, not executed: every test runs with
the real HTTP client disabled and Gemini replaced by a fake transport."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.services.gemini_api import GeminiAPIError
from evaluation import gemini_evaluation_framework as fw

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    class Blocked:
        def __init__(self, *a, **k):
            raise AssertionError("network access attempted in a test")
    monkeypatch.setattr(httpx, "AsyncClient", Blocked)
    import app.services.gemini_api as gemini_api

    async def blocked(*a, **k):
        raise AssertionError("real Gemini transport used in a test")
    monkeypatch.setattr(gemini_api, "post_json", blocked)


@pytest.fixture
def dataset(tmp_path):
    rows = [json.loads(line) for line in (ROOT / "evaluation/final_test_scenarios_v3.jsonl").read_text().splitlines()]
    chosen = []
    for label in ("legitimate", "fraudulent", "borderline"):
        chosen += [r for r in rows if r["ground_truth"] == label][:2]
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in chosen), encoding="utf-8")
    return path


def verification_json(recommendation="AUTO_APPROVE", red_flags=()):
    return {"authenticity_score": 81, "risk_level": "LOW", "recommendation": recommendation,
            "summary": "synthetic", "dimension_scores": {"plausibility": 80, "specificity": 80,
                                                          "red_flag_score": 90, "documentation": 75},
            "red_flags": list(red_flags), "positive_signals": [], "missing_requirements": []}


class FakeGemini:
    """Counts calls by stage; can fail with a given category after N successful calls."""

    def __init__(self, recommendation="AUTO_APPROVE", fail_after=None, category="QUOTA_EXHAUSTED"):
        self.calls, self.recommendation, self.fail_after, self.category = [], recommendation, fail_after, category
        self.payloads = []

    async def __call__(self, url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise GeminiAPIError(stage, self.category, 429)
        self.calls.append(stage)
        self.payloads.append(json.dumps(payload))
        if stage == "embedding":
            return {"embeddings": [{"values": [1.0, float(i % 3), 0.5]} for i in range(len(payload["requests"]))]}
        text = json.dumps(verification_json(self.recommendation))
        return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


def run(cases, store, fake, configs=fw.CONFIGS, max_calls=1000):
    transport = fw.BudgetedTransport(fake, "test-key", max_calls) if fake else None
    return asyncio.run(fw.execute(cases, configs, store, transport, "f" * 64))


# ----------------------------------------------------------------- planning
def test_plan_is_offline_deterministic_and_counts_calls(dataset):
    first = fw.main(["plan", "--dataset", str(dataset), "--sample-per-cluster", "0"])
    second = fw.main(["plan", "--dataset", str(dataset), "--sample-per-cluster", "0"])
    assert first["case_ids"] == second["case_ids"] and first["cases"] == 6
    assert first["api_calls_required"] == {"generation": 12, "embedding": 6}


def test_sampling_is_stratified_and_reproducible():
    rows = fw.load_cases(ROOT / "evaluation/final_test_scenarios_v3.jsonl")
    a = fw.sample_cases(rows, 2, 7, "scenario_family")
    b = fw.sample_cases(rows, 2, 7, "scenario_family")
    assert [c["case_id"] for c in a] == [c["case_id"] for c in b] and len(a) == 60


@pytest.mark.parametrize("env,key,budget,message", [
    ("", "k", "5", "SEVAFUND_GEMINI_EVAL_APPROVED"), ("1", "", "5", "GEMINI_API_KEY"), ("1", "k", None, "--max-calls")])
def test_execute_refuses_without_explicit_approval_key_and_budget(dataset, tmp_path, monkeypatch, env, key, budget, message):
    monkeypatch.setenv(fw.APPROVAL_ENV, env)
    monkeypatch.setattr(fw.settings, "GEMINI_API_KEY", key)
    argv = ["execute", "--dataset", str(dataset), "--output-root", str(tmp_path / "out"), "--sample-per-cluster", "0"]
    if budget:
        argv += ["--max-calls", budget]
    with pytest.raises(SystemExit, match=message):
        fw.main(argv)
    assert not (tmp_path / "out").exists()          # nothing written when refused


def test_non_synthetic_data_requires_authorization_and_is_redacted(tmp_path):
    row = {"case_id": "R1", "ground_truth": "legitimate", "synthetic": False,
           "input": {"title": "Help Asha Verma", "category": "MEDICAL", "story": "Call Asha on +91 98450 12345.",
                     "goal_amount": 1, "beneficiary_name": "Asha Verma",
                     "documents": [{"title": "Bill", "doc_type": "BILL", "content": "Asha Verma, a@b.example"}]}}
    path = tmp_path / "real.jsonl"
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(fw.DataAuthorizationError):
        fw.load_cases(path)
    cleaned = fw.redact(fw.load_cases(path, data_authorization="DPA-2026-01")[0])
    text = json.dumps(cleaned)
    assert "Asha" not in text and "98450" not in text and "a@b.example" not in text


# ---------------------------------------------------------- execution & cache
def test_offline_mode_runs_only_offline_configurations(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    store = fw.Store(tmp_path / "s")
    run(cases, store, None)
    configs = {r["config"] for r in store.cache.values() if r["stage"] == "result"}
    assert configs == {"heuristics_only", "heuristics_lexical"}


def test_full_run_caches_and_resume_makes_no_new_calls(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    store = fw.Store(tmp_path / "s")
    fake = FakeGemini()
    state = run(cases, store, fake)
    assert state["stopped_reason"] is None
    assert fake.calls.count("generation") == 12 and fake.calls.count("embedding") == 6
    again = FakeGemini()
    run(cases, fw.Store(tmp_path / "s"), again)       # fresh process: cache reloaded from disk
    assert again.calls == []


def test_quota_exhaustion_stops_records_failure_and_resumes(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    store = fw.Store(tmp_path / "s")
    state = run(cases, store, FakeGemini(fail_after=3))
    assert state["stopped_reason"] == "QUOTA_EXHAUSTED"
    failures = store.failures()
    assert failures and all(f["category"] == "QUOTA_EXHAUSTED" for f in failures)
    assert all(set(f) <= {"config", "case_id", "stage", "category", "status_code", "exception_type",
                          "duration_seconds", "at"} for f in failures)       # no prompt, no text, no key
    resumed = FakeGemini()
    run(cases, fw.Store(tmp_path / "s"), resumed)
    assert 0 < len(resumed.calls) < 18                 # only the jobs that were not cached
    report = fw.report(cases, fw.CONFIGS, fw.Store(tmp_path / "s"))
    assert report["paired_complete_cases"] == 6


def test_budget_is_enforced(dataset, tmp_path):
    state = run(fw.load_cases(dataset), fw.Store(tmp_path / "s"), FakeGemini(), max_calls=2)
    assert state["stopped_reason"] == "BUDGET_EXHAUSTED" and sum(state["calls_this_run"].values()) == 2


def test_gemini_failure_is_never_replaced_by_heuristic_fallback(dataset, tmp_path):
    cases = fw.load_cases(dataset)[:1]
    store = fw.Store(tmp_path / "s")
    run(cases, store, FakeGemini(fail_after=0, category="SERVER_ERROR"), configs=["gemini_no_rag"])
    assert not [r for r in store.cache.values() if r["config"] == "gemini_no_rag"]
    assert store.failures()[0]["category"] == "SERVER_ERROR"


def test_api_key_is_not_written_anywhere(dataset, tmp_path):
    run(fw.load_cases(dataset), fw.Store(tmp_path / "s"), FakeGemini(fail_after=4))
    for path in (tmp_path / "s").iterdir():
        assert "test-key" not in path.read_text()


# -------------------------------------------------------------- hybrid & report
def test_hybrid_lets_gemini_escalate_but_never_approve_or_activate(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    run(cases, fw.Store(tmp_path / "flag"), FakeGemini(recommendation="FLAG_FOR_REVIEW"))
    flagged = [r for r in fw.Store(tmp_path / "flag").cache.values() if r["config"] == "hybrid"]
    assert flagged and all(r["decision"] != "APPROVED" for r in flagged)
    run(cases, fw.Store(tmp_path / "ok"), FakeGemini(recommendation="AUTO_APPROVE"))
    for record in [r for r in fw.Store(tmp_path / "ok").cache.values() if r["config"] == "hybrid"]:
        assert record["workflow_state"] != "VERIFIED_ACTIVE"
        if record["v3_decision"] in ("NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED"):
            assert record["decision"] == record["v3_decision"]
    assert fw.hybrid_decision(cases[0], None)["decision"] in ("VERIFICATION_ERROR", "FLAG_FOR_REVIEW",
                                                              "NEEDS_MORE_INFORMATION", "REJECTED")


def test_report_separates_retrieval_verification_and_reliability(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    run(cases, fw.Store(tmp_path / "s"), FakeGemini())
    result = fw.report(cases, fw.CONFIGS, fw.Store(tmp_path / "s"))
    assert set(result["verification_on_paired_subset"]) == set(fw.CONFIGS)
    assert {"heuristics_lexical", "gemini_rag"} <= set(result["retrieval"])
    assert result["reliability"]["gemini_rag"]["success_rate"] == 1.0
    assert result["coverage"] == {c: 1.0 for c in fw.CONFIGS}


def test_retrieval_metrics_use_gold_evidence_when_available():
    case = {"input": {"documents": [{"title": "Bill"}, {"title": "Ledger"}]}, "gold_evidence_titles": ["Ledger"]}
    metrics = fw.retrieval_metrics(case, [{"title": "Bill"}, {"title": "Ledger"}])
    assert metrics["document_coverage"] == 1.0 and metrics["gold_recall_at_k"] == 1.0 and metrics["gold_mrr"] == 0.5


def test_every_counted_call_is_exactly_one_http_request_and_rate_limit_stops(dataset, tmp_path):
    seen = []

    async def recording(url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        seen.append(max_attempts)
        raise GeminiAPIError(stage, "RATE_LIMIT", 429)
    state = run(fw.load_cases(dataset), fw.Store(tmp_path / "s"), recording)
    assert seen == [1]                                   # no hidden retries; stopped after the first 429
    assert state["stopped_reason"] == "RATE_LIMIT"


def test_plan_reports_both_quota_scenarios(dataset):
    plan = fw.main(["plan", "--dataset", str(dataset), "--sample-per-cluster", "0"])
    days = plan["estimated_days_at_quota"]
    assert days["if_embedding_quota_is_separate_per_model"] == 1      # 12 generation calls / 20 per day
    assert days["if_all_calls_share_the_generation_quota"] == 1       # 18 calls / 20 per day
    full = fw.build_plan([{"case_id": str(i), "ground_truth": "legitimate", "input": {}} for i in range(60)],
                         fw.CONFIGS, dataset, 2, 1, 20, 1000)
    assert full["estimated_days_at_quota"] == {**full["estimated_days_at_quota"],
                                               "if_embedding_quota_is_separate_per_model": 6,
                                               "if_all_calls_share_the_generation_quota": 9}


def test_pilot_selection_is_balanced_across_labels_and_categories():
    rows = fw.load_cases(ROOT / "evaluation/final_test_scenarios_v3.jsonl")
    pilot = fw.pilot_cases(rows, 1)
    assert sorted(c["ground_truth"] for c in pilot) == ["borderline", "fraudulent", "legitimate"]
    assert len({c["input"]["category"] for c in pilot}) == 3
    assert [c["case_id"] for c in fw.pilot_cases(rows, 1)] == [c["case_id"] for c in pilot]


# ------------------------------------------------ controls for the 10-group evaluation
def run_capped(cases, store, fake, generation=None, embedding=None, max_calls=1000, stop_after=None):
    limits = {k: v for k, v in (("generation", generation), ("embedding", embedding)) if v is not None}
    transport = fw.BudgetedTransport(fake, "test-key", max_calls, stage_limits=limits,
                                     already_used=store.cumulative_calls())
    return asyncio.run(fw.execute(cases, fw.CONFIGS, store, transport, "f" * 64,
                                  max_transient_generation_failures=stop_after))


def test_per_stage_caps_are_enforced_independently(dataset, tmp_path):
    fake = FakeGemini()
    state = run_capped(fw.load_cases(dataset), fw.Store(tmp_path / "s"), fake, generation=4, embedding=10)
    assert fake.calls.count("generation") == 4 and state["stopped_reason"] == "BUDGET_EXHAUSTED"
    assert state["cumulative_calls"]["generation"] == 4


def test_budget_is_cumulative_across_resumed_runs(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    first = FakeGemini(fail_after=3, category="QUOTA_EXHAUSTED")
    state = run_capped(cases, fw.Store(tmp_path / "s"), first, generation=5)
    assert state["stopped_reason"] == "QUOTA_EXHAUSTED"
    used = state["cumulative_calls"]["generation"]          # successful and refused requests both count
    assert used == first.calls.count("generation") + 1
    second = FakeGemini()
    state = run_capped(cases, fw.Store(tmp_path / "s"), second, generation=5)
    assert second.calls.count("generation") == 5 - used     # only the remaining approved budget is spent
    assert state["cumulative_calls"]["generation"] == 5 and state["stopped_reason"] == "BUDGET_EXHAUSTED"


def test_early_stop_after_second_timeout_or_server_error(dataset, tmp_path):
    fake = FakeGemini(fail_after=0, category="READ_TIMEOUT")
    state = run_capped(fw.load_cases(dataset), fw.Store(tmp_path / "s"), fake, stop_after=1)
    assert state["stopped_reason"] == "EARLY_STOP_TRANSIENT_FAILURES"
    assert state["transient_generation_failures_total"] == 2
    again = FakeGemini()
    resumed = run_capped(fw.load_cases(dataset), fw.Store(tmp_path / "s"), again, stop_after=1)
    assert again.calls == [] and resumed["stopped_reason"] == "EARLY_STOP_TRANSIENT_FAILURES"


def test_explanations_are_recorded_for_gemini_and_v3(dataset, tmp_path):
    store = fw.Store(tmp_path / "s")
    run(fw.load_cases(dataset)[:2], store, FakeGemini(recommendation="FLAG_FOR_REVIEW"))
    gemini = next(r for r in store.cache.values() if r["config"] == "gemini_rag" and r["stage"] == "result")
    hybrid = next(r for r in store.cache.values() if r["config"] == "hybrid")
    assert {"summary", "red_flag_texts", "missing_requirements", "risk_level"} <= set(gemini)
    assert {"v3_reasons", "v3_finding_codes", "escalated_by_gemini"} <= set(hybrid)


def test_eval_v1_selection_and_report_on_a_fake_run(tmp_path):
    """The 10-group selection is valid and the report renders from a fake (network-free) run."""
    import sys
    sys.path.insert(0, str(ROOT / "evaluation"))
    import report_gemini_eval_v1 as rep
    from select_gemini_eval_v1_cases import build
    rows, manifest = build()
    assert len({m["group"] for m in manifest}) == 10
    assert sorted(m["label"] for m in manifest).count("fraudulent") == 4
    assert {m["category"] for m in manifest} == {"MEDICAL", "EDUCATION", "COMMUNITY"}
    selection_dir = tmp_path / "sel"
    selection_dir.mkdir()
    (selection_dir / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (selection_dir / "selection.json").write_text(json.dumps({"classification": "diagnostic", "cases": manifest}))
    experiment = tmp_path / "exp"
    state = run_capped(rows, fw.Store(experiment), FakeGemini(recommendation="FLAG_FOR_REVIEW"), generation=20, embedding=10,
                       stop_after=1)
    assert state["cumulative_calls"] == {"generation": 20, "embedding": 10}
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({"git_head": "x", "working_tree_clean": True,
                                  "files": {"app/services/rag.py": rep.sha(ROOT / "app/services/rag.py")}}))
    report = rep.build(experiment, selection_dir / "selection.json", tmp_path / "none.json", freeze)
    text = rep.render(report, "Interpretation.")
    assert report["metrics"]["gemini_rag"]["tp"] == 4 and report["metrics"]["gemini_rag"]["legit_escalated"] == 4
    for section in ("## 1.", "## 4.", "## 7.", "## 9.", "## 11."):
        assert section in text


# ---------------------------------------------------------------- hybrid v2 configurations
class FakeDatedGemini(FakeGemini):
    """Returns the dated schema (structured concerns) for generation requests."""

    async def __call__(self, url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        if stage == "generation" and self.fail_after is not None and self.calls.count("generation") >= self.fail_after:
            raise GeminiAPIError(stage, self.category, 503)
        self.calls.append(stage)
        self.payloads.append(json.dumps(payload))
        if stage == "embedding":
            return {"embeddings": [{"values": [1.0, float(i % 3), 0.5]} for i in range(len(payload["requests"]))]}
        body = {**verification_json("NEEDS_MORE_INFO", ["Diagnosis not specified"]),
                "concerns": [{"category": "MISSING_INFORMATION", "description": "Diagnosis not specified"}]}
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(body)}]}, "finishReason": "STOP"}]}


def test_v2_configs_share_retrieval_and_cost_one_generation_call(dataset, tmp_path):
    cases = fw.load_cases(dataset)
    plan = fw.build_plan(cases, ["gemini_rag", "hybrid", "gemini_rag_dated", "hybrid_v2"], dataset, None, 1, 20, 1000)
    assert plan["api_calls_required"] == {"generation": 12, "embedding": 6}
    fake = FakeDatedGemini()
    transport = fw.BudgetedTransport(fake, "test-key", 100)
    asyncio.run(fw.execute(cases, ["gemini_rag", "gemini_rag_dated", "hybrid_v2"], fw.Store(tmp_path / "s"), transport, "f" * 64))
    assert fake.calls.count("embedding") == 6 and fake.calls.count("generation") == 12
    store = fw.Store(tmp_path / "s")
    dated = [r for r in store.cache.values() if r.get("config") == "gemini_rag_dated"]
    v2 = [r for r in store.cache.values() if r.get("config") == "hybrid_v2"]
    assert len(dated) == 6 and all("reference_date" in r for r in dated)
    assert any("VERIFICATION DATE" in p for p in fake.payloads)
    assert len(v2) == 6 and all(r["workflow_state"] != "VERIFIED_ACTIVE" for r in v2)
    # a generic information gap on Gemini's information request never escalates under hybrid v2
    assert all(r["decision"] != "FLAG_FOR_REVIEW" or r["v3_decision"] in ("FLAG_FOR_REVIEW", "REJECTED") for r in v2)


def test_dated_call_failure_is_recorded_and_counts_toward_the_stop_rule(dataset, tmp_path):
    fake = FakeDatedGemini(fail_after=0, category="SERVER_ERROR")
    transport = fw.BudgetedTransport(fake, "test-key", 100)
    store = fw.Store(tmp_path / "s")
    state = asyncio.run(fw.execute(fw.load_cases(dataset), ["gemini_rag_dated", "hybrid_v2"], store, transport, "f" * 64,
                                   max_transient_generation_failures=1))
    assert state["stopped_reason"] == "EARLY_STOP_TRANSIENT_FAILURES"
    assert fake.calls.count("generation") == 0 and state["transient_generation_failures_total"] == 2
    assert not [r for r in store.cache.values() if r.get("config") == "hybrid_v2"]
