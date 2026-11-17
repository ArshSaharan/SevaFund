"""Seal and verify the whole evaluation kit (tooling, pre-registration, protocol, author/labeller kit, fixtures).

Sealing requires the owner-approved pre-registration (status APPROVED) and happens before any independent case
exists.  A live run refuses to start unless the kit verifies.  Standard library only.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import config

EXTRA_FILES = ["evaluation/independent_test_protocol_v5.md", "evaluation/run_independent_test_v5.py",
               "evaluation/score_independent_test_v5.py", "evaluation/prepare_independent_data_v5.py",
               "tests/test_independent_v5.py", "evaluation/hybrid_v3_freeze.json", "evaluation/freeze_hybrid_v3.py"]


def kit_files() -> List[str]:
    files = set(EXTRA_FILES)
    for directory in (config.PACKAGE, config.KIT):
        for path in directory.rglob("*"):
            if path.is_file() and path != config.KIT_MANIFEST and "__pycache__" not in path.parts:
                files.add(str(path.relative_to(config.ROOT)))
    return sorted(files)


def current() -> dict:
    return {p: config.sha256_file(config.ROOT / p) for p in kit_files() if (config.ROOT / p).exists()}


def seal() -> dict:
    prereg = config.load_prereg()
    if prereg.get("status") != "APPROVED":
        raise SystemExit("Refusing to seal: the pre-registration has not been approved (status must be APPROVED)")
    if config.KIT_MANIFEST.exists():
        raise SystemExit(f"{config.KIT_MANIFEST.name} exists; the kit is never re-sealed in place")
    missing = [p for p in kit_files() if not (config.ROOT / p).exists()]
    if missing:
        raise SystemExit(f"Refusing to seal: missing kit files {missing}")
    manifest = {"sealed_at_utc": datetime.now(timezone.utc).isoformat(), "files": current(),
                "prereg_version": prereg["version"],
                "rule": "Sealed before any independent case exists. Any change invalidates the live run."}
    config.KIT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"sealed": True, "files": len(manifest["files"])}


def verify() -> dict:
    if not config.KIT_MANIFEST.exists():
        return {"valid": False, "problems": ["the kit has not been sealed"]}
    manifest = json.loads(config.KIT_MANIFEST.read_text(encoding="utf-8"))
    now = current()
    changed = sorted(p for p, h in manifest["files"].items() if now.get(p) != h)
    added = sorted(set(now) - set(manifest["files"]))
    return {"valid": not changed and not added, "problems": [f"changed: {changed}", f"added: {added}"] if changed or added else [],
            "changed": changed, "added": added}
