"""Stage 3: cross-document evidence consistency.

Each check compares normalized fields across the campaign text and the
uploaded documents and returns ``Finding`` objects that name the conflicting
fields, their values, the documents (with page/chunk), a confidence, and why
the conflict matters.

Two principles are enforced here:
  * formatting differences (name order, initials, date/amount styles,
    organisation abbreviations, identifier punctuation) are not conflicts;
  * agreement is never treated as proof.  These checks can only find
    contradictions; they cannot establish that a document is authentic.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set

from .config import VerifierConfig
from .extraction import CAMPAIGN_TEXT, is_org_name, org_kind
from .money import format_inr
from .normalize import MATCH, MISMATCH, PARTIAL, compare_names, compare_orgs, name_tokens
from .schemas import CaseInput, DocumentEvidence, ExtractedField, Finding, FindingValue, Severity

_STOPWORDS = {"the", "and", "for", "with", "from", "that", "this", "has", "have", "been", "will", "are", "was",
              "our", "their", "his", "her", "its", "into", "per", "nos", "not", "but", "who", "which", "under",
              "advised", "admission", "planned"}
_GENERIC_SERVICE = {"surgery", "treatment", "care", "course", "year", "first", "second", "third", "work", "supply",
                    "patient", "programme", "program", "month", "week", "general", "total", "new", "one", "two",
                    "operation", "procedure", "class", "followed", "day", "donor", "recipient", "taught", "full",
                    "time", "level", "standard", "service", "item", "purpose", "community", "family", "village"}
_COMPARABLE_IDS = {"patient_id": 0.85, "inpatient_id": 0.85, "roll_no": 0.85, "enrolment_no": 0.85,
                   "application_no": 0.8, "admission_no": 0.85, "student_id": 0.85, "pan": 0.85,
                   "registration_no": 0.75}
_ID_LABELS = {"patient_id": "patient/hospital number", "inpatient_id": "in-patient number", "roll_no": "roll number",
              "enrolment_no": "enrolment number", "application_no": "application number",
              "admission_no": "admission number", "student_id": "student ID", "pan": "PAN",
              "registration_no": "registration number"}
_BILLING_TITLE = re.compile(r"\bbill\b|invoice|receipt", re.I)
_ESTIMATE_TITLE = re.compile(r"estimate|quotation|proforma", re.I)


@dataclass
class Context:
    case: CaseInput
    claim: DocumentEvidence
    docs: List[DocumentEvidence]            # readable documents only
    texts: Dict[int, str]
    config: VerifierConfig
    concepts: Dict[str, Set[str]] = field(default_factory=dict)   # category lexicon (may be empty)

    @property
    def is_organisation(self) -> bool:
        kind = (self.case.beneficiary_type or "").upper()
        return kind in {"ORGANISATION", "ORGANIZATION", "NGO"} or is_org_name(self.case.beneficiary_name or "")


def value_of(label: str, item: ExtractedField, shown: Optional[str] = None) -> FindingValue:
    return FindingValue(field=label, value=shown if shown is not None else str(item.raw),
                        document=item.source.document, doc_index=item.source.doc_index,
                        page=item.source.page, chunk=item.source.chunk)


def campaign_value(label: str, value: str) -> FindingValue:
    return FindingValue(field=label, value=value, document=CAMPAIGN_TEXT)


def full_name_occurs(name: str, text: str) -> bool:
    """True when the complete name is visible despite extraction punctuation loss."""
    tokens = name_tokens(name)
    if not tokens:
        return False
    pattern = r"(?<![A-Za-z])" + r"[\W_]+".join(re.escape(token) for token in tokens) + r"(?![A-Za-z])"
    return bool(re.search(pattern, text or "", re.I))


# ------------------------------------------------------------------ identity
def check_identity(ctx: Context) -> List[Finding]:
    """Is each document about the person the campaign is for?"""
    name = ctx.case.beneficiary_name
    if not name or ctx.is_organisation:
        return []
    findings = []
    for doc in ctx.docs:
        if full_name_occurs(name, ctx.texts.get(doc.index, "")):
            continue
        subjects = doc.of("person", "subject")
        if not subjects:
            continue
        verdicts = [(compare_names(name, subject.value), subject) for subject in subjects]
        if any(verdict[0] == MATCH for verdict, _ in verdicts):
            continue
        partial = [(verdict, subject) for verdict, subject in verdicts if verdict[0] == PARTIAL]
        if partial:
            verdict, subject = partial[0]
            findings.append(Finding(
                kind="identity", code="IDENTITY_UNCERTAIN", dimension="identity", component="cross_document",
                severity=Severity.UNCERTAIN, confidence=0.5,
                summary=f"The name on '{doc.title}' only partly matches the beneficiary ({verdict[2]}).",
                explanation="The document may belong to the beneficiary under another form of their name, or to "
                            "someone else. This cannot be settled from the papers alone.",
                values=[campaign_value("beneficiary name", name), value_of("person named in document", subject)]))
            continue
        verdict, subject = max(verdicts, key=lambda pair: pair[1].confidence)
        reliable = subject.confidence >= 0.7
        findings.append(Finding(
            kind="identity", code="IDENTITY_MISMATCH", dimension="identity", component="cross_document",
            severity=Severity.MATERIAL if reliable else Severity.UNCERTAIN,
            confidence=round(verdict[1] * (1.0 if reliable else 0.55), 2),
            summary=f"'{doc.title}' is in a different person's name ({verdict[2]}).",
            explanation="A supporting document issued to someone other than the beneficiary does not evidence "
                        "the beneficiary's need and may have been borrowed from another case.",
            values=[campaign_value("beneficiary name", name), value_of("person named in document", subject)]))
    return findings


# --------------------------------------------------------------- identifiers
def check_identifiers(ctx: Context) -> List[Finding]:
    """The same kind of identifier should not take different values across the dossier."""
    findings = []
    for family, confidence in _COMPARABLE_IDS.items():
        seen: Dict[str, ExtractedField] = {}
        for doc in [ctx.claim] + ctx.docs:
            for item in doc.of("identifier", family):
                if not any(item.value == known or (len(min(item.value, known, key=len)) >= 4 and
                           (item.value.endswith(known) or known.endswith(item.value))) for known in seen):
                    seen[item.value] = item
        if len(seen) > 1 and len({item.source.doc_index for item in seen.values()}) > 1:
            label = _ID_LABELS[family]
            findings.append(Finding(
                kind="identifier", code="IDENTIFIER_CONFLICT", dimension="identity", component="cross_document",
                severity=Severity.MATERIAL, confidence=confidence,
                summary=f"The {label} differs between documents.",
                explanation=f"Records for one person or organisation at one institution carry a single {label}. "
                            "Different values suggest the documents relate to different records, or that one "
                            "was altered.",
                values=[value_of(label, item) for item in seen.values()]))
    return findings


# -------------------------------------------------------------------- amounts
@dataclass
class CostSummary:
    doc: DocumentEvidence
    total: Optional[ExtractedField]
    balance: Optional[ExtractedField]
    paid: float
    covered: float
    currency: Optional[str] = None

    @property
    def need(self) -> Optional[Decimal]:
        if self.balance is not None:
            return self.balance.value
        if self.total is not None:
            return max(self.total.value - self.paid - self.covered, Decimal(0))
        return None

    @property
    def issued(self) -> Optional[str]:
        dates = [f.value for f in self.doc.of("date", "issue")]
        return max(dates) if dates else None


def summarize_costs(ctx: Context) -> List[CostSummary]:
    """One summary per issuer: when an issuer provides several cost documents
    (e.g. an estimate and its revision) the most recent one stands."""
    summaries = []
    for doc in ctx.docs:
        if "cost" not in doc.evidence_classes:
            continue
        valid = lambda role: [f for f in doc.of("amount", role) if f.value is not None]
        totals, balances = valid("total"), valid("balance")
        currencies = {f.currency for f in totals + balances if f.currency}
        # A single document may contain multiple price schedules/currencies. Do
        # not combine unlike values into one outstanding balance.
        if len(currencies) > 1:
            continue
        currency = next(iter(currencies), "INR")
        totals = [f for f in totals if (f.currency or "INR") == currency]
        balances = [f for f in balances if (f.currency or "INR") == currency]
        summaries.append(CostSummary(
            doc=doc, total=max(totals, key=lambda f: f.value) if totals else None,
            balance=balances[-1] if balances else None,
            paid=sum((f.value for f in valid("paid") if (f.currency or "INR") == currency), Decimal(0)),
            covered=sum((f.value for f in valid("covered") if (f.currency or "INR") == currency), Decimal(0)),
            currency=currency))
    latest: List[CostSummary] = []
    for summary in summaries:
        for index, kept in enumerate(latest):
            same_issuer = (summary.doc.issuer and kept.doc.issuer
                           and compare_orgs(summary.doc.issuer, kept.doc.issuer)[0] == MATCH)
            if same_issuer:
                newer = (summary.issued or "") > (kept.issued or "") or (
                    summary.issued == kept.issued and (summary.need or 0) > (kept.need or 0))
                if newer:
                    latest[index] = summary
                break
        else:
            latest.append(summary)
    return latest


def check_cost_statements(ctx: Context) -> List[Finding]:
    """Two cost documents from the same issuer that disagree on the total.

    A later-dated document is treated as a revision (harmless); documents with
    the same date, or without dates, cannot both be right.
    """
    findings = []
    costed = []
    for doc in ctx.docs:
        # The headline figure of a demand: its total, or the amount due when no total is stated.
        totals = [f for f in doc.of("amount", "total") if f.value] or [f for f in doc.of("amount", "balance") if f.value]
        if "cost" in doc.evidence_classes and totals and doc.issuer:
            dates = sorted(f.value for f in doc.of("date", "issue"))
            currencies = {f.currency or "INR" for f in totals}
            if len(currencies) == 1:
                costed.append((doc, max(totals, key=lambda f: f.value), dates[-1] if dates else None))
    for i, (left, left_total, left_date) in enumerate(costed):
        for right, right_total, right_date in costed[i + 1:]:
            if (left_total.currency or "INR") != (right_total.currency or "INR"):
                continue
            if compare_orgs(left.issuer, right.issuer)[0] != MATCH:
                continue
            if left_date and right_date and left_date != right_date:
                continue
            high, low = max(left_total.value, right_total.value), min(left_total.value, right_total.value)
            if high > low * (Decimal(1) + Decimal(str(ctx.config.amount_tolerance))):
                findings.append(Finding(
                    kind="amount", code="COST_STATEMENTS_DISAGREE", dimension="financial",
                    component="cross_document", severity=Severity.MATERIAL, confidence=0.65,
                    summary=f"'{left.title}' and '{right.title}' from the same issuer give different totals "
                            "for the same date.",
                    explanation="An institution issues one figure for one demand on one date. Two different "
                                "totals mean at least one statement is inaccurate or altered.",
                    values=[value_of("total", left_total, f"{left_total.currency or 'INR'} {left_total.value}"),
                            value_of("total", right_total, f"{right_total.currency or 'INR'} {right_total.value}")]))
    return findings


def check_amounts(ctx: Context) -> List[Finding]:
    """Reconcile the requested amount with the documented cost and what is still outstanding."""
    goal_currency = (ctx.case.goal_currency or "INR").upper()
    all_summaries = [s for s in summarize_costs(ctx) if s.need is not None]
    summaries = [s for s in all_summaries if (s.currency or "INR") == goal_currency]
    if not summaries:
        foreign = [s for s in all_summaries if (s.currency or "INR") != goal_currency]
        if foreign:
            currencies = sorted({s.currency or "INR" for s in foreign})
            return [Finding(kind="amount", code="CURRENCY_NOT_COMPARABLE", dimension="financial",
                            component="cross_document", severity=Severity.UNCERTAIN, confidence=0.45,
                            summary=f"The documented cost is in {', '.join(currencies)}, while the campaign goal is in {goal_currency}.",
                            explanation="No verified exchange rate is configured, so the amounts were not compared. Confirm the goal currency or provide a matching-currency cost statement.",
                            values=[value_of("documented amount", s.total or s.balance,
                                             f"{s.currency} {((s.total or s.balance).value)}") for s in foreign if (s.total or s.balance)] +
                                   [campaign_value("campaign goal currency", goal_currency)])]
        return []
    goal = Decimal(str(ctx.case.goal_amount))
    tolerance = Decimal(1) + Decimal(str(ctx.config.amount_tolerance))
    documented = sum(((s.total.value if s.total else s.need) for s in summaries), Decimal(0))
    outstanding = sum((s.need for s in summaries), Decimal(0))
    other_cover = sum((f.value for doc in ctx.docs if "cost" not in doc.evidence_classes
                       for f in doc.of("amount", "covered") if f.value is not None
                       and (f.currency or "INR") == goal_currency), Decimal(0))
    show = format_inr if goal_currency == "INR" else lambda x: f"{goal_currency} {x:,.2f}"
    values = [campaign_value("requested amount", show(goal))]
    for summary in summaries:
        if summary.total:
            values.append(value_of("documented total", summary.total, show(summary.total.value)))
        if summary.balance:
            values.append(value_of("outstanding balance", summary.balance, show(summary.balance.value)))
    if goal <= outstanding * tolerance:
        if other_cover and goal > max(outstanding - other_cover, Decimal(0)) * tolerance:
            return [Finding(
                kind="amount", code="AMOUNT_OTHER_FUNDING", dimension="financial", component="cross_document",
                severity=Severity.UNCERTAIN, confidence=0.5,
                summary="Another document records funding towards this cost that the request does not deduct.",
                explanation="If part of the cost is already financed elsewhere, the appeal should be for the "
                            "remainder; the campaigner should confirm how the other funding is applied.",
                values=values)]
        return []
    if goal <= documented * tolerance:
        zero = outstanding <= 0
        material = zero or goal >= Decimal(str(ctx.config.amount_material_ratio)) * outstanding
        return [Finding(
            kind="amount", code="AMOUNT_EXCEEDS_BALANCE", dimension="financial", component="cross_document",
            severity=Severity.MATERIAL if material else Severity.UNCERTAIN, confidence=0.85 if zero else 0.75 if material else 0.5,
                summary=f"The request of {show(goal)} exceeds the outstanding balance of "
                        f"{show(outstanding)} shown in the documents.",
            explanation="The documents show that part or all of the cost has already been paid or covered, so "
                        "the amount still needed is lower than the amount being raised.",
            values=values)]
    ratio = goal / documented if documented else float("inf")
    cited = [f for f in ctx.claim.of("amount", "total", "balance")
             if f.value and (f.currency or goal_currency) == goal_currency and f.value > documented * tolerance]
    material = ratio >= Decimal(str(ctx.config.amount_material_ratio))
    if cited:
        values.append(value_of("amount the story attributes to the documents", cited[0], show(cited[0].value)))
    return [Finding(
        kind="amount", code="AMOUNT_UNSUPPORTED", dimension="financial", component="cross_document",
        severity=Severity.MATERIAL if material else Severity.UNCERTAIN,
        confidence=(0.85 if cited else 0.8) if material else 0.5,
        summary=f"The request of {show(goal)} is {ratio:.1f}x the documented cost of {show(documented)}.",
        explanation=("The campaign text attributes a higher figure to the documents than they actually show. "
                     if cited and material else "") +
                    "Funds requested beyond the documented cost are unsupported; a modest excess may be "
                    "legitimate incidental cost, a large one needs explanation and evidence.",
        values=values)]


# ---------------------------------------------------------------- institution
def claimed_institutions(ctx: Context) -> List[str]:
    if ctx.is_organisation and ctx.case.beneficiary_name:
        return [ctx.case.beneficiary_name]
    return [f.value for f in ctx.claim.of("organisation") if org_kind(f.value) == "institution"]


def check_institution(ctx: Context) -> List[Finding]:
    """A core document that never mentions the claimed institution but is issued
    by, or certifies, a different comparable institution is a contradiction.
    Suppliers, diagnostic centres, banks and public authorities are expected to
    differ from the claimed institution and are not compared."""
    claimed = claimed_institutions(ctx)
    if not claimed:
        return []
    findings = []
    for doc in ctx.docs:
        names = ([doc.issuer] if doc.issuer else []) + [f.value for f in doc.of("organisation")]
        if not names or any(compare_orgs(c, n)[0] == MATCH for c in claimed for n in names):
            continue
        principal = [f for f in doc.of("organisation", "named") if org_kind(f.value) == "institution"]
        principal_names = [f.value for f in principal]
        if doc.issuer and doc.issuer_kind == "institution":
            principal_names.insert(0, doc.issuer)
        different = [p for p in principal_names if all(compare_orgs(c, p)[0] == MISMATCH for c in claimed)]
        partial = [p for p in principal_names if any(compare_orgs(c, p)[0] == PARTIAL for c in claimed)]
        if not different and not partial:
            continue
        other = (different or partial)[0]
        findings.append(Finding(
            kind="institution", code="INSTITUTION_MISMATCH" if different else "INSTITUTION_UNCERTAIN",
            dimension="institutional", component="cross_document",
            severity=Severity.MATERIAL if different else Severity.UNCERTAIN, confidence=0.75 if different else 0.45,
            summary=f"'{doc.title}' concerns {other}, not {claimed[0]}.",
            explanation="The campaign names one institution but this document was issued by or for another and "
                        "does not mention the claimed one, so it does not support the claim as stated.",
            values=[campaign_value("institution named by the campaign", claimed[0]),
                    FindingValue(field="institution on document", value=other, document=doc.title, doc_index=doc.index,
                                 page=(principal[0].source.page if principal else None),
                                 chunk=(principal[0].source.chunk if principal else 1))]))
    return findings


# ----------------------------------------------------------------- chronology
def _dates(doc: DocumentEvidence, *roles: str) -> List[ExtractedField]:
    return doc.of("date", *roles)


def check_chronology(ctx: Context) -> List[Finding]:
    findings = []
    reference = ctx.case.submitted_on
    admissions = [(f, doc) for doc in ctx.docs for f in _dates(doc, "admission")]
    discharges = [(f, doc) for doc in ctx.docs for f in _dates(doc, "discharge")]

    def finding(code, confidence, summary, explanation, values, severity=Severity.MATERIAL):
        findings.append(Finding(kind="chronology", code=code, dimension="narrative", component="cross_document",
                                severity=severity, confidence=confidence, summary=summary,
                                explanation=explanation, values=values))

    for discharge, _ in discharges:
        for admission, _ in admissions:
            if discharge.value < admission.value:
                finding("DISCHARGE_BEFORE_ADMISSION", 0.9, "A discharge date precedes the admission date.",
                        "A patient cannot be discharged before being admitted; the records cannot both be right.",
                        [value_of("admission date", admission), value_of("discharge date", discharge)])
                break
    for doc in ctx.docs:
        label = f"{doc.doc_type.replace('_', ' ')} {doc.title}"
        billing = ("cost" in doc.evidence_classes and _BILLING_TITLE.search(label)
                   and not _ESTIMATE_TITLE.search(label))
        if billing:
            for issue in _dates(doc, "issue"):
                later = [a for a, _ in admissions if a.value > issue.value]
                if later:
                    finding("BILL_PREDATES_ADMISSION", 0.8, f"'{doc.title}' is dated before the admission it bills for.",
                            "A hospital bill is raised during or after the stay it covers. A bill dated before "
                            "the recorded admission points to an altered or unrelated document.",
                            [value_of("bill date", issue), value_of("admission date", later[0])])
                    break
        if reference:
            horizon = reference + timedelta(days=ctx.config.future_grace_days)
            for item in _dates(doc, "issue", "meeting", "admission", "discharge", "procedure"):
                if date.fromisoformat(item.value) > horizon:
                    finding("FUTURE_DATED_DOCUMENT", 0.85,
                            f"'{doc.title}' records {'an' if item.role[0] in 'aeiou' else 'a'} {item.role} date "
                            "after the campaign was submitted.",
                            "A record of something that has already happened cannot carry a date later than the "
                            "day it was uploaded.",
                            [value_of(f"{item.role} date", item),
                             campaign_value("campaign submitted on", reference.isoformat())])
                    break
            for item in _dates(doc, "due"):
                if date.fromisoformat(item.value) < reference - timedelta(days=ctx.config.lapsed_deadline_days):
                    finding("DEADLINE_LAPSED", 0.5, f"The payment deadline on '{doc.title}' passed long ago.",
                            "The document may be out of date; the current position should be confirmed.",
                            [value_of("due date", item), campaign_value("campaign submitted on", reference.isoformat())],
                            Severity.UNCERTAIN)
                    break
            if "cost" in doc.evidence_classes:
                issued = [date.fromisoformat(f.value) for f in _dates(doc, "issue")]
                if issued and max(issued) < reference - timedelta(days=ctx.config.stale_document_days):
                    finding("STALE_COST_DOCUMENT", 0.45, f"'{doc.title}' is more than "
                            f"{ctx.config.stale_document_days // 30} months old.",
                            "Costs and circumstances change; an up-to-date document is needed.",
                            [value_of("document date", doc.of("date", "issue")[0])], Severity.UNCERTAIN)
    return findings


# -------------------------------------------------------------------- service
def stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def content_tokens(text: str) -> Set[str]:
    tokens = {stem(t) for t in re.findall(r"[a-z][a-z0-9]{2,}", (text or "").casefold())}
    return {t for t in tokens if t not in _STOPWORDS and t not in _GENERIC_SERVICE}


def concept_groups(tokens: Set[str], concepts: Dict[str, Set[str]]) -> Set[str]:
    return {name for name, words in concepts.items() if tokens & words}


def _class_level(text: str) -> Optional[str]:
    match = re.search(r"\b(?:class|std|standard|grade)\.?\s+([ivx]{1,4}|\d{1,2})\b", text or "", re.I)
    return match.group(1).upper() if match else None


def check_service(ctx: Context) -> List[Finding]:
    """Does each document describe the same treatment, course or work as the campaign?

    A conflict is reported only on positive evidence that the document is
    about something else; a description that merely cannot be related to the
    claim (e.g. a paraphrase) is reported as uncertain.
    """
    claim_text = f"{ctx.case.title} {ctx.case.story}"
    for organisation in ctx.claim.of("organisation"):
        claim_text = claim_text.replace(organisation.raw, " ")   # a hospital's name is not a treatment
    claim_tokens = content_tokens(claim_text)
    claim_groups = concept_groups(claim_tokens, ctx.concepts)
    claim_level = _class_level(claim_text)
    per_doc = {}
    for doc in ctx.docs:
        described = [(f, content_tokens(f.value)) for f in doc.of("service")]
        described = [(f, tokens) for f, tokens in described if tokens or _class_level(f.value)]
        if described:
            per_doc[doc.index] = (doc, described)

    def supported(item, tokens):
        level = _class_level(item.value)
        if level and claim_level:
            return level == claim_level
        return bool(tokens & claim_tokens) or bool(concept_groups(tokens, ctx.concepts) & claim_groups)

    anchored = {index: [tokens for item, tokens in described if supported(item, tokens)]
                for index, (doc, described) in per_doc.items()}
    findings = []
    for index, (doc, described) in per_doc.items():
        if anchored[index]:
            continue                      # at least one description in this document matches the claim
        item, tokens = max(described, key=lambda pair: pair[0].confidence)
        groups = concept_groups(tokens, ctx.concepts)
        level = _class_level(item.value)
        others = [t for other, token_sets in anchored.items() if other != index for t in token_sets]
        unrelated_to_others = bool(others) and not any(
            tokens & other or groups & concept_groups(other, ctx.concepts) for other in others)
        if level and claim_level and level != claim_level:
            code, severity, confidence = "SERVICE_LEVEL_CONFLICT", Severity.MATERIAL, 0.8
        elif groups and claim_groups:
            code, severity, confidence = "SERVICE_CONFLICT", Severity.MATERIAL, 0.75
        elif unrelated_to_others:
            code, severity, confidence = "SERVICE_ODD_ONE_OUT", Severity.MATERIAL, 0.65
        else:
            code, severity, confidence = "SERVICE_UNRELATED", Severity.UNCERTAIN, 0.4
        findings.append(Finding(
            kind="service", code=code, dimension="narrative", component="cross_document", severity=severity,
            confidence=confidence,
            summary=f"'{doc.title}' describes \"{item.value[:90]}\", which does not correspond to what the "
                    "campaign is raising funds for.",
            explanation="When a document is for a different treatment, course or piece of work, it does not "
                        "evidence the stated purpose and the cost in it cannot be relied on.",
            values=[campaign_value("purpose stated by the campaign", ctx.case.title),
                    value_of("treatment / course / work on document", item)]))
    return findings


CHECKS = [check_identity, check_identifiers, check_cost_statements, check_amounts, check_institution,
          check_chronology, check_service]
