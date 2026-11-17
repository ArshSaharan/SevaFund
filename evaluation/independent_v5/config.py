"""Paths and the pre-registration (standard library only)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALUATION = ROOT / "evaluation"
PACKAGE = Path(__file__).resolve().parent
KIT = EVALUATION / "independent_test_v5"
PREREG_PATH = KIT / "preregistration.json"
FIXTURES = PACKAGE / "engineering_fixtures"
EXCLUSION_REGISTRY = PACKAGE / "exclusion_registry.json"
KIT_MANIFEST = KIT / "kit_manifest.json"
RUNS = EVALUATION / "runs"
APPROVAL_ENV = "SEVAFUND_GEMINI_EVAL_APPROVED"

LABELS = ("legitimate", "fraudulent", "borderline")
DOCUMENTATION = ("complete", "incomplete")
DECISIONS = ("APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR")
DETECTION = {"FLAG_FOR_REVIEW", "REJECTED"}
CHECKS = ("BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION")
ENVIRONMENT_PARTIES = CHECKS + ("COST_ISSUER",)
RESPONSES = {"CONFIRMED", "CONTRADICTED", "UNREACHABLE", "INCONCLUSIVE"}
SYSTEMS = ("hybrid_v3", "hybrid_v2", "v3_alone")


def load_prereg(path: Path = PREREG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list:
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            rows.append(json.loads(line))
    return rows


def stratum(truth: str, documentation: str) -> str:
    """F fraudulent, B borderline, I legitimate-incomplete, L legitimate-complete."""
    if truth == "fraudulent":
        return "F"
    if truth == "borderline":
        return "B"
    return "I" if documentation == "incomplete" else "L"
