"""V3 evidence tiers: one focused request for critical gaps, optional evidence is advisory."""
from typing import List

from .consistency import Context, full_name_occurs
from .normalize import MATCH, compare_names, compare_orgs
from .schemas import Requirement


def assess_requirements(ctx: Context, category_aware: bool = True) -> List[Requirement]:
    readable = ctx.docs
    category = (ctx.case.category or "").upper() if category_aware else "OTHER"
    if "MED" in category:
        relevant = {"clinical", "cost"}
        examples = "a treatment record, hospital estimate, or current bill"
    elif "EDU" in category or "SCHOOL" in category:
        relevant = {"enrollment", "cost"}
        examples = "an admission/enrolment record or fee statement"
    elif any(tag in category for tag in ("COMM", "SOCIAL", "NGO", "DISASTER")):
        relevant = {"authorization", "cost", "beneficiary_info", "org_identity"}
        examples = "a work order, attributable quotation, or beneficiary/organisation record"
    else:
        relevant = {"cost", "clinical", "enrollment", "authorization", "beneficiary_info"}
        examples = "one record that supports the campaign's central purpose"
    supported = [doc.title for doc in readable if relevant.intersection(doc.evidence_classes)]
    result = [Requirement(
        key="critical_claim_support",
        description="At least one readable document supports the campaign's central purpose or material request.",
        satisfied=bool(supported), satisfied_by=supported,
        request="Please provide " + examples + "." if not supported else "",
        critical=True, tier="critical")]

    # Identity is requested only where the dossier contains no identity record.
    # A positive mismatch is handled as a contradiction by the identity check.
    beneficiary = ctx.case.beneficiary_name
    identity_docs = []
    if beneficiary and not ctx.is_organisation:
        for doc in readable:
            if (full_name_occurs(beneficiary, ctx.texts.get(doc.index, ""))
                    or any(compare_names(beneficiary, field.value)[0] == MATCH
                           for field in doc.of("person", "subject"))):
                identity_docs.append(doc.title)
    elif beneficiary:
        for doc in readable:
            named_orgs = ([doc.issuer] if doc.issuer else []) + [field.value for field in doc.of("organisation")]
            if ("org_identity" in doc.evidence_classes or "authorization" in doc.evidence_classes
                    or full_name_occurs(beneficiary, ctx.texts.get(doc.index, ""))
                    or any(compare_orgs(beneficiary, candidate)[0] == MATCH for candidate in named_orgs)):
                identity_docs.append(doc.title)
    if beneficiary:
        result.append(Requirement(
            key="beneficiary_identity", description="A record links the named beneficiary to the campaign.",
            satisfied=bool(identity_docs), satisfied_by=identity_docs,
            request="Please provide a beneficiary identity or institutional record." if not identity_docs else "",
            critical=True, tier="critical"))

    # These contribute context but are not mandatory when a primary claim record
    # is present; missing optional items must not generate a beneficiary request.
    cost_docs = [doc.title for doc in readable if "cost" in doc.evidence_classes]
    detailed_cost = [doc.title for doc in readable if "cost" in doc.evidence_classes
                     and doc.traceability >= ctx.config.min_traceability]
    result.append(Requirement(
        key="cost_traceability", description="Cost evidence has issuer, date, reference or signatory details.",
        satisfied=bool(detailed_cost), satisfied_by=detailed_cost, request="", critical=False, tier="optional"))
    if "MED" in category:
        clinical = [doc.title for doc in readable if "clinical" in doc.evidence_classes]
        result.append(Requirement(key="clinical_detail", description="Clinical detail corroborates a medical request.",
                                  satisfied=bool(clinical), satisfied_by=clinical, request="",
                                  critical=False, tier="optional"))
    elif "EDU" in category or "SCHOOL" in category:
        enrollment = [doc.title for doc in readable if "enrollment" in doc.evidence_classes]
        result.append(Requirement(key="enrolment_detail", description="An enrolment record corroborates an education request.",
                                  satisfied=bool(enrollment), satisfied_by=enrollment, request="",
                                  critical=False, tier="optional"))
    elif any(tag in category for tag in ("COMM", "SOCIAL", "NGO", "DISASTER")):
        authorization = [doc.title for doc in readable if "authorization" in doc.evidence_classes]
        result.append(Requirement(key="project_authorization", description="A formal project authorization is available.",
                                  satisfied=bool(authorization), satisfied_by=authorization, request="",
                                  critical=False, tier="optional"))
    return result
