"""Validate V3 package/config hashes against the freeze manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_digest(path):
    files = {item.name: digest(item) for item in sorted(path.glob("*.py"))}
    return {"files": files, "combined": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def verify():
    manifest = json.loads((ROOT / "evaluation/development_candidate_v3_freeze.json").read_text())
    config_path = ROOT / "evaluation/development_candidate_v3_config.json"
    dataset_path = ROOT / manifest["development_dataset"]["path"]
    actual_v3 = package_digest(ROOT / "app/services/development_verifier_v3")
    actual_v2 = package_digest(ROOT / "app/services/development_verifier_v2")
    checks = {
        "v3_package": actual_v3["combined"] == manifest["v3_package"]["combined"],
        "configuration_file": digest(config_path) == manifest["config_sha256"],
        "configuration_content": json.loads(config_path.read_text()) == manifest["config"],
        "development_dataset": digest(dataset_path) == manifest["development_dataset"]["sha256"],
        "v2_package": actual_v2["combined"] == manifest["v2_package"]["combined"],
    }
    return {"valid": all(checks.values()), "checks": checks,
            "v3_package_sha256": actual_v3["combined"], "v2_package_sha256": actual_v2["combined"],
            "config_sha256": digest(config_path), "development_dataset_sha256": digest(dataset_path)}


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit("Frozen V3 state changed")
