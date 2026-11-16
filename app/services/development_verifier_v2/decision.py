"""Stages 5-6: risk scoring and decision generation.

Decision policy (evaluated in this order; every branch records its reasons):

1. REJECTED            - at least two *independent* material findings (different
                         dimensions) each with confidence >= reject_confidence.
                         Missing or incomplete documentation can never reach here.
2. FLAG_FOR_REVIEW     - any material finding with confidence >= flag_confidence.
                         If a stage also failed, the flag stands and the failure
                         is reported alongside it.
3. VERIFICATION_ERROR  - any stage, document load or external reasoner failed.
                         Incomplete verification is never treated as legitimacy.
4. NEEDS_MORE_INFORMATION - unsatisfied evidence requirement, uncertain finding,
                         or a material finding below flag_confidence.
5. APPROVED            - every requirement satisfied and no findings.  This is
                         approval on documentary consistency only: independent
                         confirmation with the issuer is recorded as unavailable.

Scores are descriptive (0-100 per dimension, higher = fewer concerns) and are
not used as thresholds; the decision depends only on findings and
requirements, so it can be explained without reference to a weighted sum.
"""
from typing import Dict, List

from .config import VerifierConfig
from .schemas import Decision, Finding, Requirement, Severity, VerificationDecision

DIMENSIONS = ("identity", "financial", "institutional", "narrative", "documentation")
WEIGHTS = {"identity": 0.2, "financial": 0.25, "institutional": 0.15, "narrative": 0.15, "documentation": 0.25}
RISK = {Decision.APPROVED: "LOW", Decision.NEEDS_MORE_INFORMATION: "MEDIUM", Decision.FLAG_FOR_REVIEW: "HIGH",
        Decision.REJECTED: "CRITICAL", Decision.VERIFICATION_ERROR: "UNKNOWN"}


def score(findings: List[Finding], requirements: List[Requirement], document_count: int) -> Dict[str, float]:
    scores = {name: 100.0 for name in DIMENSIONS}
    for finding in findings:
        weight = 60 if finding.severity == Severity.MATERIAL else 25
        scores[finding.dimension] = max(0.0, scores[finding.dimension] - weight * finding.confidence)
    if requirements:
        scores["documentation"] = round(100.0 * sum(r.satisfied for r in requirements) / len(requirements), 1)
    if document_count == 0:
        scores["documentation"] = 0.0
    return {name: round(value, 1) for name, value in scores.items()}


def decide(findings: List[Finding], requirements: List[Requirement], errors: List[str],
           config: VerifierConfig, document_count: int) -> VerificationDecision:
    material = [f for f in findings if f.severity == Severity.MATERIAL and f.confidence >= config.flag_confidence]
    strong = [f for f in material if f.confidence >= config.reject_confidence]
    unmet = [r for r in requirements if not r.satisfied]
    reasons: List[str] = []
    influencing: List[str] = []

    if len({f.dimension for f in strong}) >= 2:
        decision = Decision.REJECTED
        reasons.append("Two or more independent, high-confidence contradictions were found in different "
                       "verification dimensions.")
        reasons += [f.summary for f in strong]
        influencing = sorted({f.dimension for f in strong})
    elif material:
        decision = Decision.FLAG_FOR_REVIEW
        reasons.append("A material contradiction in the evidence needs a human reviewer.")
        reasons += [f.summary for f in material]
        influencing = sorted({f.dimension for f in material})
        if errors:
            reasons.append("Verification was also incomplete: " + "; ".join(errors))
    elif errors:
        decision = Decision.VERIFICATION_ERROR
        reasons.append("Verification could not be completed, so the campaign cannot be approved automatically.")
        reasons += errors
        influencing = ["system"]
    elif unmet or findings or not requirements:
        decision = Decision.NEEDS_MORE_INFORMATION
        if not requirements:
            reasons.append("No evidence requirements could be evaluated, so the campaign cannot be approved.")
            influencing.append("documentation")
        if document_count == 0:
            reasons.append("No supporting documents were provided. This is not evidence of fraud.")
        reasons += [f"Missing: {r.description}" for r in unmet]
        reasons += [f.summary for f in findings]
        influencing += sorted({"documentation"} if unmet else set()) + sorted({f.dimension for f in findings})
    else:
        decision = Decision.APPROVED
        reasons.append("All category-specific evidence requirements are met and no contradiction was found "
                       "across the campaign and its documents.")
        influencing = ["documentation", "identity", "financial", "institutional", "narrative"]

    scores = score(findings, requirements, document_count)
    authenticity = round(sum(scores[name] * WEIGHTS[name] for name in DIMENSIONS), 1)
    requests = [r.request for r in unmet]
    requests += [f"Clarify: {f.summary}" for f in findings
                 if decision == Decision.NEEDS_MORE_INFORMATION]
    uncertainty = ["Documents were checked only against each other and the campaign text. Their authenticity was "
                   "not confirmed with the issuing hospital, institution or registrar; consistent documents can "
                   "still be fabricated."]
    if decision == Decision.APPROVED:
        uncertainty.append("Approval rests on documentary consistency only; issuer confirmation is recommended "
                           "before funds are released.")
    return VerificationDecision(
        decision=decision, risk_level=RISK[decision], authenticity_score=authenticity, dimension_scores=scores,
        influencing_dimensions=list(dict.fromkeys(influencing)), reasons=reasons, findings=findings,
        requirements=requirements, information_requests=list(dict.fromkeys(requests)),
        uncertainty_notes=uncertainty, errors=errors)
