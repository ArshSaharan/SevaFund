"""Freeze V3 source/configuration and preservation hashes before final-test generation."""
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.development_verifier_v2.config import DEFAULT_CONFIG as V2_CONFIG
from app.services.development_verifier_v3.config import DEFAULT_CONFIG as V3_CONFIG, ENGINE_VERSION

PACKAGE_V3 = ROOT / "app/services/development_verifier_v3"
PACKAGE_V2 = ROOT / "app/services/development_verifier_v2"
CONFIG_PATH = ROOT / "evaluation/development_candidate_v3_config.json"
MANIFEST_PATH = ROOT / "evaluation/development_candidate_v3_freeze.json"
DEV_DATA = ROOT / "evaluation/development_scenarios_v3.jsonl"
PREVIOUS = {
    "evaluation/development_scenarios_v2.jsonl": "V2 development corpus",
    "evaluation/independent_benchmark_100.jsonl": "previous 100-case diagnostic benchmark",
    "evaluation/independent_test_150.jsonl": "previous 150-case diagnostic benchmark",
    "evaluation/fundraising_scenarios.jsonl": "previous 200-case holdout corpus",
    "evaluation/development_candidate_v2_freeze.json": "V2 freeze manifest",
    "evaluation/runs/development_candidate_v2_all_20261115T205042Z/report.md": "V2 prior evaluation report",
    "evaluation/runs/development_candidate_v2_all_20261115T205042Z/results.json": "V2 prior machine-readable results",
    "evaluation/runs/development_candidate_v2_all_20261116T100640Z/report.md": "V2 reproducibility report created before V3 freeze",
    "evaluation/runs/development_candidate_v2_all_20261116T100640Z/results.json": "V2 reproducibility results created before V3 freeze",
    "evaluation/development_scenarios_v3_initial.jsonl": "initial V3 development corpus, superseded because generated issue dates crossed submission date",
    "evaluation/development_scenarios_v3_contradiction_only.jsonl": "V3 corpus used by a superseded run before consistent-fabrication fraud families were included",
    "evaluation/runs/development_v3_20261116T093632Z/results.json": "superseded V3 run with invalid future document dates",
    "evaluation/runs/development_v3_revised_20261116T094732Z/results.json": "superseded contradiction-only V3 development run",
    "evaluation/runs/development_v3_frozen_20261116T100612Z/results.json": "final V3 development comparison and ablation results",
    "evaluation/results.json": "existing evaluation results",
    "evaluation/results_live_gemini.json": "existing live-Gemini results",
}
PRODUCTION_FILES = (
    "app/services/ai_verifier.py", "app/services/fraud_detector.py", "app/services/rag.py",
)
EXPECTED_PRODUCTION = {
    "app/services/ai_verifier.py": "3a3b857c8bf658d1400b1a9c92eb1f19a60a405e17ba86199be7298bcd1bc9c8",
    "app/services/fraud_detector.py": "f47e641743d1d66272cf36d6bfa2053245bbf2b68bf15b19075fab41cf97279f",
    "app/services/rag.py": "95b14980be44fd6b658cd4025a0c24a90447a53fb212f42cede257b2f4f71309",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_hash(path):
    files = {item.name: digest(item) for item in sorted(path.glob("*.py"))}
    return {"files": files, "combined": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def freeze():
    if MANIFEST_PATH.exists():
        raise SystemExit(f"Refusing to overwrite existing freeze: {MANIFEST_PATH}")
    if (ROOT / "evaluation/final_test_scenarios_v3.jsonl").exists():
        raise SystemExit("Final test corpus already exists; freeze must precede final-test creation")
    v3 = package_hash(PACKAGE_V3)
    v2 = package_hash(PACKAGE_V2)
    previous_freeze = json.loads((ROOT / "evaluation/development_candidate_v2_freeze.json").read_text())
    if v2["combined"] != previous_freeze["v2_package"]["combined"]:
        raise SystemExit("V2 source differs from its existing freeze manifest")
    config = V3_CONFIG.model_dump()
    CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    config_hash = digest(CONFIG_PATH)
    preserved = {}
    for rel, description in PREVIOUS.items():
        path = ROOT / rel
        if path.exists():
            preserved[rel] = {"description": description, "sha256": digest(path)}
    production = {rel: digest(ROOT / rel) for rel in PRODUCTION_FILES}
    if production != EXPECTED_PRODUCTION:
        raise SystemExit("A production verifier/RAG file differs from the V3-task baseline")
    manifest = {
        "engine_version": ENGINE_VERSION,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "v3_package": v3,
        "config": config,
        "config_digest": V3_CONFIG.digest(),
        "config_sha256": config_hash,
        "development_dataset": {"path": str(DEV_DATA.relative_to(ROOT)), "sha256": digest(DEV_DATA),
                                "rows": sum(1 for line in DEV_DATA.read_text(encoding="utf-8").splitlines() if line)},
        "v2_package": v2,
        "v2_config_digest": V2_CONFIG.digest(),
        "python": sys.version.split()[0],
        "dependencies": {name: importlib.metadata.version(name) for name in ("pydantic", "pytest")},
        "production_file_sha256_at_freeze": production,
        "preserved_prior_artifacts": preserved,
        "commands": {
            "regression_tests": "PYTHONPATH=.. ../.venv/bin/pytest -p no:cacheprovider -q ../tests/test_development_verifier_v3.py ../tests/test_development_verifier_v2.py ../tests/test_development_dataset_v3.py",
            "development_evaluation": "./.venv/bin/python -B evaluation/evaluate_development_verifier_v3.py --tag development_v3_frozen",
            "generate_final_test_once": "./.venv/bin/python -B evaluation/generate_final_test_v3.py",
            "evaluate_final_test_once": "./.venv/bin/python -B evaluation/evaluate_final_test_v3.py",
        },
        "evaluation_scope": "offline heuristic verifier; no Gemini generation, Gemini embeddings, or semantic RAG",
        "final_test_state": "not generated or evaluated at freeze time",
        "authorship_limit": "Synthetic scenarios were authored by the project agent; no independent author or human adjudicator was available.",
        "post_freeze_rule": "Any change to a V3 package source file or frozen configuration invalidates the final test. Do not tune against final-test outcomes.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"freeze_manifest": str(MANIFEST_PATH), "config": str(CONFIG_PATH),
                      "v3_package_sha256": v3["combined"], "config_sha256": config_hash,
                      "development_dataset_sha256": manifest["development_dataset"]["sha256"],
                      "v2_package_sha256": v2["combined"], "production_files": production}, indent=2))


if __name__ == "__main__":
    freeze()
