"""Freeze (and verify) the improved V3 + Gemini implementation (hybrid v2) before any independent testing.

    python evaluation/freeze_hybrid_v2.py freeze    # writes evaluation/hybrid_v2_freeze.json (refuses to overwrite)
    python evaluation/freeze_hybrid_v2.py verify    # exit 1 if anything recorded has changed
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MANIFEST = Path(__file__).with_name("hybrid_v2_freeze.json")
PACKAGES = ["app/services/development_gemini_verification", "app/services/development_verifier_v3",
            "app/services/development_approval_workflow"]
FILES = ["evaluation/gemini_evaluation_framework.py", "evaluation/evaluate_development_verifier_v3.py",
         "evaluation/run_independent_test_v4.py", "evaluation/validate_independent_submission.py",
         "app/services/ai_verifier.py", "app/services/rag.py", "app/services/gemini_api.py", "app/config.py",
         "app/schemas/ai.py", "app/services/fraud_detector.py"]


def current() -> dict:
    paths = list(FILES) + [str(p.relative_to(ROOT)) for pkg in PACKAGES for p in sorted((ROOT / pkg).glob("*.py"))]
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def freeze():
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.name} already exists; a frozen implementation is never re-frozen in place")
    from app.services.development_gemini_verification.config import POLICY_VERSION, SETTINGS, digest
    manifest = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
        "policy_version": POLICY_VERSION, "policy_settings": SETTINGS, "policy_digest": digest(),
        "files": current(),
        "development_evidence": "In-sample re-scoring of the 10-case gemini_eval_v1_3_6 outputs only "
                                "(runs/hybrid_policy_rescoring_*). The policy was designed after inspecting those outputs.",
        "rule": "Any change to a recorded file invalidates independent-test results; a new version needs a new freeze "
                "and a new test set. Do not tune against the independent test.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"frozen": True, "files": len(manifest["files"]), "git_head": manifest["git_head"]}))


def verify() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    now = current()
    changed = sorted(p for p in manifest["files"] if now.get(p) != manifest["files"][p])
    added = sorted(set(now) - set(manifest["files"]))
    return {"valid": not changed and not added, "changed": changed, "added": added,
            "policy_version": manifest["policy_version"]}


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "freeze":
        freeze()
    else:
        result = verify()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["valid"] else 1)
