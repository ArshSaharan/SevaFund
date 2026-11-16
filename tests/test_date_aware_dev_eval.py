"""Offline tests for the date-aware prompt development evaluation runner (no network: fake transports only)."""
import asyncio
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_date_aware_dev_eval as ev  # noqa: E402

REF = date(2026, 11, 17)


def test_reference_date_is_asia_kolkata_not_utc():
    # 19:58 UTC on 16 November is already 17 November in India.
    assert ev.reference_date(datetime(2026, 11, 16, 19, 58, tzinfo=timezone.utc)) == date(2026, 11, 17)
    assert ev.reference_date(datetime(2026, 11, 16, 18, 29, tzinfo=timezone.utc)) == date(2026, 11, 16)


def test_rendering_is_relative_to_the_reference_date():
    cases = ev.render_cases(REF)
    assert len(cases) == 8 and all(c["input"]["submitted_on"] == "2026-11-17" for c in cases)
    bill = next(d for d in cases[2]["input"]["documents"] if d["title"] == "Final bill")["content"]
    assert "Bill Date: 14/12/2026" in bill                     # d+27
    notice = cases[1]["input"]["documents"][0]["content"]
    assert "valid until 05/11/2026" in notice                  # d-12
    assert "{{" not in json.dumps(cases)


def test_preflight_passes_without_network():
    check = ev.preflight(ev.render_cases(REF))
    assert check["ok"], check["problems"]
    assert check["distinctness"]["all_distinct"]
    assert all(v["complete"] for v in check["retrieval_coverage"].values())


def _run(tmp_path, fake, monkeypatch=None):
    run_dir = tmp_path / "run"
    cases = ev.start_run(run_dir, REF, "dry-run")
    transport, audit = ev.make_transport(fake, "k", run_dir, 0.0)
    state = asyncio.run(ev.run_jobs(cases, transport, audit, ev.RunLog(run_dir)))
    return run_dir, state


def test_happy_path_uses_exactly_ten_requests_and_no_embeddings(tmp_path):
    fake = ev.FakeGemini()
    run_dir, state = _run(tmp_path, fake)
    attempts = ev.RunLog(run_dir).attempts()
    assert fake.requests == 10 and state["http_requests_total"] == 10
    assert [a["system"] for a in attempts] == ["C"] * 8 + ["B", "B"]
    assert [a["case_id"] for a in attempts if a["system"] == "B"] == ev.B_CASES
    http = [json.loads(l) for l in (run_dir / "http_requests.jsonl").read_text().splitlines()]
    assert {h["stage"] for h in http} == {"generation"}


def test_one_transient_failure_is_retried_from_the_production_prompt_budget(tmp_path):
    fake = ev.FakeGemini(failures={3: ("SERVER_ERROR", 503)})
    run_dir, state = _run(tmp_path, fake)
    attempts = ev.RunLog(run_dir).attempts()
    assert fake.requests == 10
    retried = [a for a in attempts if a["transient_retry"]]
    assert len(retried) == 1 and retried[0]["case_id"] == "DA-03" and retried[0]["status"] == "OK"
    assert [a["case_id"] for a in attempts if a["system"] == "B" and a["http_requests"]] == ["DA-01"]
    assert attempts[-1]["stop"] == "BUDGET_EXHAUSTED" and attempts[-1]["http_requests"] == 0     # DA-06 never sent


def test_second_transient_failure_stops_for_good(tmp_path):
    fake = ev.FakeGemini(failures={2: ("READ_TIMEOUT", None), 4: ("SERVER_ERROR", 503)})
    run_dir, state = _run(tmp_path, fake)
    assert state["stopped_reason"] == "EARLY_STOP_TRANSIENT_FAILURES" and fake.requests == 4
    assert ev.RunLog(run_dir).final_stop() == "EARLY_STOP_TRANSIENT_FAILURES"


def test_quota_stop_is_resumable_within_the_same_budget(tmp_path):
    fake = ev.FakeGemini(failures={1: ("QUOTA_EXHAUSTED", 429)})
    run_dir, state = _run(tmp_path, fake)
    assert state["stopped_reason"] == "QUOTA_EXHAUSTED" and fake.requests == 1
    log = ev.RunLog(run_dir)
    assert log.final_stop() is None
    transport, audit = ev.make_transport(ev.FakeGemini(), "k", run_dir, 0.0)
    state = asyncio.run(ev.run_jobs(ev.load_run_cases(run_dir), transport, audit, log))
    assert state["http_requests_total"] == 10                    # 1 quota-rejected + 9 more; never 11
    assert [a["case_id"] for a in log.attempts() if a["system"] == "B" and a["http_requests"]] == ["DA-01"]


def test_budget_transport_never_exceeds_ten_requests(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fake = ev.FakeGemini()
    transport, audit = ev.make_transport(fake, "k", run_dir, 0.0)
    payload = {"generationConfig": {"responseSchema": {"properties": {}}}}

    async def hammer():
        results = []
        for _ in range(12):
            try:
                await transport("https://x/models/m:generateContent", "k", payload, "generation", 1)
                results.append("ok")
            except ev.GeminiAPIError as exc:
                results.append(exc.category)
        return results
    results = asyncio.run(hammer())
    assert results.count("ok") == 10 and results[10:] == ["BUDGET_EXHAUSTED"] * 2 and fake.requests == 10

    async def embed():
        await transport("https://x/models/e:batchEmbedContents", "k", {}, "embedding", 1)
    with pytest.raises(ev.GeminiAPIError):
        asyncio.run(embed())


def test_execute_refuses_without_approval_model_or_budget(monkeypatch):
    monkeypatch.delenv(ev.fw.APPROVAL_ENV, raising=False)
    with pytest.raises(SystemExit, match="explicit approval"):
        ev.main(["execute", "--max-calls", "10"])
    monkeypatch.setenv(ev.fw.APPROVAL_ENV, "1")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    with pytest.raises(SystemExit, match="gemini-3.6-flash"):
        ev.main(["execute", "--max-calls", "10"])
    monkeypatch.setenv("GEMINI_MODEL", ev.MODEL)
    monkeypatch.setattr(ev.settings, "GEMINI_MODEL", ev.MODEL)
    with pytest.raises(SystemExit, match="at most 10"):
        ev.main(["execute", "--max-calls", "11"])


def test_failed_requests_are_scored_fail_closed_and_analysis_runs(tmp_path):
    fake = ev.FakeGemini(failures={5: ("JSON_PARSE_ERROR", 200)}, recommendation="AUTO_APPROVE")
    run_dir, _ = _run(tmp_path, fake)
    result = ev.analyze(run_dir)
    rows = {r["case_id"]: r for r in result["rows"]}
    assert rows["DA-05"]["C"]["gemini_status"] == "FAILED" and rows["DA-05"]["C"]["decision"] != "APPROVED"
    assert result["api_usage"]["within_limit"] and result["api_usage"]["http_requests"] == 10
    checks = result["safety_checks"]
    for name in ("S6_gemini_cannot_authorise_or_reject_alone", "S7_external_confirmation_mandatory",
                 "S8_api_failures_fail_closed"):
        assert checks[name]["result"] == "PASS", (name, checks[name])
    assert checks["S3_strict_no_ungrounded_explicit_recommendation_escalates"]["result"] == "FAIL"   # by design


def test_metrics_definitions():
    rows = [{"case_id": "f1", "label": "fraudulent", "scenario_type": "X", "S": {"decision": "FLAG_FOR_REVIEW"}},
            {"case_id": "f2", "label": "fraudulent", "scenario_type": "X", "S": {"decision": "APPROVED"}},
            {"case_id": "l1", "label": "legitimate", "scenario_type": "LEGITIMATE_INCOMPLETE_INFORMATION",
             "S": {"decision": "APPROVED"}},
            {"case_id": "l2", "label": "legitimate", "scenario_type": "X", "S": {"decision": "NEEDS_MORE_INFORMATION"}},
            {"case_id": "u", "label": "legitimate", "scenario_type": "X", "S": {"decision": None}}]
    m = ev.system_metrics(rows, "S")
    assert m["cases_scored"] == 4 and m["recall"] == 0.5 and m["false_positive_escalations"] == 0
    assert m["unsafe_approvals"] == ["f2"] and m["unresolved_information_approvals"] == ["l1"]
    assert m["manual_reviews"] == 1 and m["information_requests"] == 1


def test_injected_api_failures_never_approve_on_any_scenario():
    for case in ev.render_cases(REF):
        ctx = ev._context(case)
        out = ev.injections(case, ctx)
        for name, x in out["api_failures"].items():
            assert x["gemini_status"] == "FAILED", (case["case_id"], name)
            assert x["decision"] != "APPROVED" and x["state"] not in ("ELIGIBLE_PENDING_CONFIRMATION", "VERIFIED_ACTIVE")
