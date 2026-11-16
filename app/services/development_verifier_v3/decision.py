"""V3 decision policy; missing optional evidence never creates a follow-up request."""
from typing import Dict, List

from .config import VerifierConfig
from .schemas import Decision, Finding, Requirement, Severity, VerificationDecision

DIMENSIONS = ("identity", "financial", "institutional", "narrative", "documentation")
WEIGHTS = {"identity": 0.20, "financial": 0.25, "institutional": 0.15, "narrative": 0.15, "documentation": 0.25}
RISK = {Decision.APPROVED: "LOW", Decision.NEEDS_MORE_INFORMATION: "MEDIUM", Decision.FLAG_FOR_REVIEW: "HIGH",
        Decision.REJECTED: "CRITICAL", Decision.VERIFICATION_ERROR: "UNKNOWN"}


def score(findings: List[Finding], requirements: List[Requirement], document_count: int) -> Dict[str, float]:
    values = {name: 100.0 for name in DIMENSIONS}
    for finding in findings:
        penalty = 60 if finding.severity == Severity.MATERIAL else 25
        values[finding.dimension] = max(0.0, values[finding.dimension] - penalty * finding.confidence)
    critical = [item for item in requirements if item.critical]
    if critical:
        values["documentation"] = 100.0 * sum(item.satisfied for item in critical) / len(critical)
    elif document_count == 0:
        values["documentation"] = 0.0
    return {name: round(value, 1) for name, value in values.items()}


def decide(findings: List[Finding], requirements: List[Requirement], errors: List[str],
           config: VerifierConfig, document_count: int) -> VerificationDecision:
    material = [f for f in findings if f.severity == Severity.MATERIAL and f.confidence >= config.flag_confidence]
    strong = [f for f in material if f.confidence >= config.reject_confidence]
    unmet = [r for r in requirements if r.critical and not r.satisfied]
    reasons: List[str] = []
    influencing: List[str] = []

    # Rejection requires independent, high-confidence evidence across dimensions.
    if len({f.dimension for f in strong}) >= 2:
        decision = Decision.REJECTED
        reasons.append("Independent high-confidence contradictions affect multiple verification dimensions.")
        reasons.extend(f.summary for f in strong)
        influencing = sorted({f.dimension for f in strong})
    elif material:
        decision = Decision.FLAG_FOR_REVIEW
        reasons.append("A material inconsistency requires human review; this is not an automatic fraud finding.")
        reasons.extend(f.summary for f in material)
        influencing = sorted({f.dimension for f in material})
        if errors:
            reasons.append("Verification also encountered an error; manual handling is required.")
    elif errors:
        decision = Decision.VERIFICATION_ERROR
        reasons.append("Verification could not be completed. The campaign must not be auto-approved.")
        reasons.extend(errors)
        influencing = ["system"]
    elif unmet or findings or not requirements:
        decision = Decision.NEEDS_MORE_INFORMATION
        if not requirements:
            reasons.append("No critical evidence policy could be evaluated.")
            influencing.append("documentation")
        if document_count == 0:
            reasons.append("No readable supporting documents were provided; absence alone is not proof of fraud.")
        reasons.extend(f"Critical evidence missing: {r.description}" for r in unmet)
        reasons.extend(f.summary for f in findings)
        if unmet:
            influencing.append("documentation")
        influencing.extend(f.dimension for f in findings)
    else:
        decision = Decision.APPROVED
        reasons.append("Critical claim and identity evidence are present and no material contradiction was found.")
        if any(not r.satisfied for r in requirements if not r.critical):
            reasons.append("Optional supporting records are incomplete; this did not block approval.")
        influencing = ["documentation", "identity", "financial", "institutional", "narrative"]

    scores = score(findings, requirements, document_count)
    authenticity = round(sum(scores[name] * WEIGHTS[name] for name in DIMENSIONS), 1)
    requests = [r.request for r in unmet if r.request]
    requests.extend(f"Clarify: {f.summary}" for f in findings
                    if f.severity == Severity.UNCERTAIN and decision == Decision.NEEDS_MORE_INFORMATION)
    uncertainty = ["Uploaded documents were checked for consistency; they were not independently authenticated with issuers.",
                   "Payout destination verification is external to this offline verifier and remains unavailable."]
    if decision == Decision.APPROVED:
        uncertainty.append("Approval reflects documentary consistency only; external payout and issuer checks remain necessary.")
    return VerificationDecision(
        decision=decision, risk_level=RISK[decision], authenticity_score=authenticity,
        dimension_scores=scores, influencing_dimensions=list(dict.fromkeys(influencing)), reasons=reasons,
        findings=findings, requirements=requirements, information_requests=list(dict.fromkeys(requests)),
        uncertainty_notes=uncertainty, errors=errors)
