"""Stage 7: privacy-preserving audit logging.

The audit record lets a reviewer or evaluator trace a decision to its stages,
findings, document locations and dimensions without storing beneficiary
names, identifiers, document text, uploader-chosen titles or credentials.
Documents are referred to by upload position; reasons by code.  Finding values
are replaced with a short unsalted hash so equal values can still be seen to
be equal (or different) across documents.  An unsalted hash of a short value
can be brute-forced, so the record is pseudonymous, not anonymous; production
use would need a keyed hash (HMAC) with a managed secret.
"""
import hashlib
import json
import logging
from typing import Any, Dict, List

from .schemas import AuditRecord, CaseInput, Finding

logger = logging.getLogger("sevafund.development_verifier_v2.audit")


def fingerprint(case: CaseInput) -> str:
    payload = f"{case.category}|{case.title}|{case.story}|{case.goal_amount}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def value_token(value: str) -> str:
    """Stable, non-reversible token for a private value (8 hex chars)."""
    return "v:" + hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:8]


def redact_finding(finding: Finding) -> Dict[str, Any]:
    return {
        "code": finding.code, "kind": finding.kind, "dimension": finding.dimension,
        "component": finding.component, "severity": finding.severity.value,
        "confidence": finding.confidence,
        "values": [{"field": v.field, "value": value_token(v.value),
                    "document": "campaign" if v.doc_index < 0 else f"document#{v.doc_index + 1}",
                    "page": v.page, "chunk": v.chunk} for v in finding.values],
    }


class AuditTrail:
    def __init__(self, case: CaseInput, engine_version: str, config_digest: str):
        self.record = AuditRecord(case_fingerprint=fingerprint(case), engine_version=engine_version,
                                  config_digest=config_digest, category=case.category,
                                  document_count=len(case.documents))

    def stage(self, name: str, status: str = "ok", **details: Any) -> None:
        self.record.stages.append({"stage": name, "status": status, **details})

    def error(self, stage: str, exc: BaseException) -> str:
        # Only the exception type is recorded: messages can contain document text.
        message = f"{stage} failed ({type(exc).__name__})"
        self.record.errors.append(message)
        self.stage(stage, "error", exception_type=type(exc).__name__)
        return message

    def finish(self, decision: str, reason_codes: List[str], dimensions: List[str],
               findings: List[Finding]) -> AuditRecord:
        self.record.decision = decision
        self.record.reason_codes = reason_codes
        self.record.influencing_dimensions = dimensions
        self.record.findings = [redact_finding(f) for f in findings]
        logger.info("verification_audit %s", json.dumps(self.record.model_dump(), sort_keys=True))
        return self.record
