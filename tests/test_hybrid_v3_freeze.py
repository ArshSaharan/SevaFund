"""The hybrid v3 evaluation-candidate freeze verifies, detects changes, and records no secret."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import freeze_hybrid_v3 as freeze  # noqa: E402

MANIFEST = json.loads(freeze.MANIFEST.read_text(encoding="utf-8"))


def test_freeze_verifies():
    result = freeze.verify()
    assert result["valid"], result
    assert result["behavioural_fingerprint"] == MANIFEST["behavioural_fingerprint"]["sha256"]


def test_manifest_records_required_sections():
    for key in ("git", "files", "model_and_prompt", "evaluation_configuration", "behavioural_fingerprint",
                "test_results", "known_limitations", "development_data_excluded_from_independent_testing"):
        assert MANIFEST[key], key
    assert MANIFEST["policy_version"] == "hybrid-v3-dev-1"
    assert MANIFEST["api_calls_made_by_this_freeze"] == 0
    assert MANIFEST["model_and_prompt"]["hybrid_v3_calls_models"] is False
    assert MANIFEST["model_and_prompt"]["model"]["set_by_frozen_code"] is False
    assert MANIFEST["test_results"]["full_suite"]["unexpected_failures"] == []
    assert MANIFEST["test_results"]["frozen_benchmark_reproducibility"]["all_reproduced"] is True
    assert set(MANIFEST["files"]["implementation"]) == {
        f"app/services/development_hybrid_v3/{n}" for n in
        ("__init__.py", "config.py", "confirmation.py", "crossdoc.py", "dates.py", "financial.py", "policy.py")}


def test_verify_detects_a_changed_file(monkeypatch):
    real = freeze.current_hashes

    def tampered():
        hashes = real()
        path = "app/services/development_hybrid_v3/financial.py"
        hashes["implementation"][path] = "0" * 64
        return hashes

    monkeypatch.setattr(freeze, "current_hashes", tampered)
    result = freeze.verify()
    assert not result["valid"]
    assert result["changed"] == ["app/services/development_hybrid_v3/financial.py"]


def test_verify_detects_an_added_file(monkeypatch):
    real = freeze.current_hashes

    def added():
        hashes = real()
        hashes["implementation"]["app/services/development_hybrid_v3/new_rule.py"] = "1" * 64
        return hashes

    monkeypatch.setattr(freeze, "current_hashes", added)
    assert freeze.verify()["added"] == ["app/services/development_hybrid_v3/new_rule.py"]


def test_freeze_refuses_to_overwrite():
    with pytest.raises(SystemExit, match="never re-frozen"):
        freeze.freeze()


def test_manifest_contains_no_configured_key():
    from dotenv import dotenv_values
    text = freeze.MANIFEST.read_text(encoding="utf-8")
    values = [v for k, v in dotenv_values(ROOT / ".env").items() if "KEY" in k.upper() and v and len(v) >= 8]
    assert not any(v in text for v in values)
