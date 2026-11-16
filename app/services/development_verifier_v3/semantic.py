"""Semantic fraud signals that do not depend on scam keywords.

Signals are built from *concept combinations* evaluated per sentence, with
negation and conditional guards, plus structured evidence (payees, balances):

  settlement      - documents state the expense is already paid, waived or
                    fully funded while the campaign asks for it;
  eligibility     - an institutional record says the enrolment, offer or
                    registration behind the claim no longer stands;
  payment routing - funds are directed to an individual who is neither the
                    beneficiary nor a named guardian, or donors are asked to
                    pay outside the platform;
  unconfirmed     - the key document is a draft / provisional / awaiting
                    approval, so the claim is not yet established;
  plausibility    - the request is far above typical cost with no document
                    supporting it.

All of this is deterministic and offline.  It recognises ideas expressed in
ordinary administrative language; it does not understand arbitrary prose, and
that limit is stated in the evaluation report.
"""
import re
from decimal import Decimal
from typing import List

from app.services.fraud_detector import analyze_cost_benchmark

from .consistency import Context, campaign_value, summarize_costs, value_of
from .extraction import Locator, sentences
from .money import format_inr
from .normalize import MATCH, PARTIAL, compare_names
from .schemas import Finding, FindingValue, Severity

_CONDITIONAL = re.compile(r"\bif\b|\bunless\b|\bonce\b|\buntil\b|\bliable to\b|\bwill be\b|\bshall be\b|\bmay be\b|"
                          r"\bwould be\b|failing which|in case|\bto be\b|\bterms\b|\bmust\b|\bshould\b", re.I)
_ZERO_LIABILITY = re.compile(
    r"\bno dues\b|\bnil dues\b|no amount is (?:due|payable)|nothing is (?:due|payable)|"
    r"no further (?:funds?|payment|amount)s? (?:are|is) (?:required|due|needed)|no outstanding|"
    r"(?:balance|amount) (?:due|payable)[^.\n]{0,40}?\bnil\b|payable by[^.\n]{0,30}?:\s*(?:rs\.?|₹|inr)\s*0\b", re.I)
_SETTLE_VERB = re.compile(r"\b(?:paid|settled|funded|borne|covered|sanctioned|waived|waiver|reimbursed|cleared|"
                          r"supplied|completed|granted|met)\b", re.I)
_COMPLETE = re.compile(r"\bin full\b|\bfully\b|\bfull\b|\bentire\b|\bwhole\b|in its entirety|\b100\s*%", re.I)
_NOT_SETTLED = re.compile(r"\bnot (?:been |yet )*(?:paid|settled|sanctioned|received|cleared|covered)|\bunpaid\b|"
                          r"yet to be|\bpending\b|\bawaited\b", re.I)
_REIMBURSEMENT = re.compile(r"reimburs|repay|borrowed|took (?:a )?loan|loan taken|pay back", re.I)

_INELIGIBLE = re.compile(
    r"\bcancell?ed\b|struck off|\bwithdrawn\b|\brevoked\b|de-?registered|\bdefunct\b|\bdissolved\b|\blapsed\b|"
    r"\bblacklisted\b|\bdebarred\b|\bsuspended\b|\bterminated\b|\bexpelled\b|\brusticated\b|"
    r"no longer (?:holds?|recognis|recogniz|valid|enrolled|registered|a member|a student|on the rolls)|"
    r"not (?:a|an) (?:student|patient|member|registered)|no record of|no such (?:student|patient|admission)|"
    r"not authori[sz]ed|not registered|not enrolled|never (?:enrolled|admitted|registered)", re.I)
_INELIGIBLE_BENIGN = re.compile(r"cancellation charges|cancelled cheque|canceled cheque", re.I)

_UNCONFIRMED = re.compile(
    r"\bprovisional\b(?!\s+diagnosis)|\bdraft\b|\btentative\b|in-principle|in principle|\bindicative\b|"
    r"\bunaudited\b|\bnot final\b|\bnot yet\b|\bhas not\b|\bhave not\b|not (?:a|been) confirmed|\bnot valid\b|"
    r"\byet to be\b|\bawaited\b|under scrutiny|(?:is|are|remains?) pending|subject to verification|"
    r"\bunsigned\b|not been (?:approved|sanctioned|verified|issued)", re.I)
_UNCONFIRMED_BENIGN = re.compile(r"pending (?:fees|dues|bills?|amount|payment)|indicative rate|"
                                 r"investigation is in progress", re.I)

_SOLICIT = re.compile(r"\b(?:send|transfer|remit|deposit|gpay|g-pay|paytm|phonepe|pay|donate)\b", re.I)
_PERSONAL_CHANNEL = re.compile(
    r"\b(?:my|his|her|our|their|cousin|friend|uncle|aunt|brother|sister|treasurer|secretary|agent|relative|"
    r"father|mother|husband|wife|son|daughter)(?:'s)?\s+(?:\w+(?:'s)?\s+){0,2}?(?:own\s+|personal\s+|private\s+|savings\s+)*"
    r"(?:number|account|a/c|upi|gpay|wallet|qr|phone)\b", re.I)
_DIRECT = re.compile(r"\b(?:directly|straight|personally)\b[^.]{0,50}\b(?:account|number|upi|wallet|gpay|paytm|"
                     r"phonepe|cash)\b", re.I)
_OFF_PLATFORM = re.compile(r"\b(?:outside|off|bypass(?:ing)?|instead of|not through|avoid(?:ing)?)\b[^.]{0,25}"
                           r"\b(?:platform|website|site|app|sevafund|portal)\b", re.I)


def _doc_sentences(ctx: Context, index: int):
    text = ctx.texts.get(index, "")
    doc = next(d for d in ctx.docs if d.index == index)
    locator = Locator(text, doc.title, index)
    for start, end, sentence in sentences(text):
        yield sentence, locator.ref(start, end)


def _excerpt_value(label: str, ref, sentence: str) -> FindingValue:
    return FindingValue(field=label, value=" ".join(sentence.split())[:220], document=ref.document,
                        doc_index=ref.doc_index, page=ref.page, chunk=ref.chunk)


def detect_settlement(ctx: Context) -> List[Finding]:
    findings = []
    acknowledged = bool(_REIMBURSEMENT.search(ctx.case.story))
    zero_balance = {s.doc.index: s for s in summarize_costs(ctx)
                    if s.balance is not None and s.balance.value == 0 and s.total and s.total.value > 0}
    for doc in ctx.docs:
        evidence = []
        for sentence, ref in _doc_sentences(ctx, doc.index):
            if _ZERO_LIABILITY.search(sentence) and not re.search(r"\bif\b|\bunless\b|\bonce\b|\buntil\b", sentence, re.I):
                evidence.append(_excerpt_value("statement that nothing is owed", ref, sentence))
            elif (_SETTLE_VERB.search(sentence) and _COMPLETE.search(sentence)
                  and not _NOT_SETTLED.search(sentence) and not _CONDITIONAL.search(sentence)):
                evidence.append(_excerpt_value("statement that the cost is already met", ref, sentence))
        numeric = zero_balance.get(doc.index)
        if numeric:
            evidence.append(value_of("outstanding balance", numeric.balance, format_inr(0)))
        if not evidence:
            continue
        confidence = 0.9 if numeric and len(evidence) > 1 else 0.85 if numeric else 0.8
        findings.append(Finding(
            kind="settlement", code="ALREADY_SETTLED", dimension="financial", component="semantic",
            severity=Severity.UNCERTAIN if acknowledged else Severity.MATERIAL,
            confidence=0.5 if acknowledged else confidence,
            summary=f"'{doc.title}' indicates the expense has already been paid, waived or fully funded.",
            explanation=("The campaign says it is repaying money already spent; proof of that debt is needed."
                         if acknowledged else
                         "Raising money for a cost that the documents show is no longer owed is a common "
                         "double-funding pattern. The campaign does not acknowledge the earlier payment."),
            values=[campaign_value("requested amount", format_inr(ctx.case.goal_amount))] + evidence[:3]))
    return findings


def detect_ineligibility(ctx: Context) -> List[Finding]:
    findings = []
    for doc in ctx.docs:
        for sentence, ref in _doc_sentences(ctx, doc.index):
            if (_INELIGIBLE.search(sentence) and not _CONDITIONAL.search(sentence)
                    and not _INELIGIBLE_BENIGN.search(sentence)):
                findings.append(Finding(
                    kind="eligibility", code="STATUS_REVOKED", dimension="institutional", component="semantic",
                    severity=Severity.MATERIAL, confidence=0.8,
                    summary=f"'{doc.title}' states that the enrolment, offer or registration relied on by the "
                            "campaign has been cancelled, withdrawn or is not recognised.",
                    explanation="The claim depends on a status that the issuing body says no longer exists, "
                                "so the stated need cannot arise as described.",
                    values=[_excerpt_value("status recorded by the issuer", ref, sentence)]))
                break
    return findings


def detect_unconfirmed(ctx: Context) -> List[Finding]:
    findings = []
    for doc in ctx.docs:
        for sentence, ref in _doc_sentences(ctx, doc.index):
            cleaned = _UNCONFIRMED_BENIGN.sub(" ", sentence)
            if _UNCONFIRMED.search(cleaned):
                findings.append(Finding(
                    kind="unconfirmed", code="DOCUMENT_NOT_FINAL", dimension="narrative", component="semantic",
                    severity=Severity.UNCERTAIN, confidence=0.5,
                    summary=f"'{doc.title}' is provisional, a draft, or awaiting an approval.",
                    explanation="The underlying fact (cost, admission, approval or registration) is not yet "
                                "confirmed by the issuer. This is not evidence of fraud; the final document is needed.",
                    values=[_excerpt_value("wording that marks the document as not final", ref, sentence)]))
                break
    return findings


def detect_payment_routing(ctx: Context) -> List[Finding]:
    findings = []
    guardians = [f.value for doc in ctx.docs for f in doc.of("person", "guardian")]
    for doc in ctx.docs:
        for payee in doc.of("person", "payee"):
            allowed = [ctx.case.beneficiary_name] if ctx.case.beneficiary_name and not ctx.is_organisation else []
            if any(compare_names(payee.value, name)[0] in (MATCH, PARTIAL) for name in allowed + guardians):
                continue
            values = [campaign_value("beneficiary", ctx.case.beneficiary_name or "(not stated)"),
                      value_of("payee named for the funds", payee)]
            values += [value_of("payment handle", f) for f in doc.of("identifier", "upi")[:1]]
            findings.append(Finding(
                kind="payment_routing", code="THIRD_PARTY_PAYEE", dimension="financial", component="semantic",
                severity=Severity.MATERIAL, confidence=0.8,
                summary=f"'{doc.title}' directs payment to an individual who is not the beneficiary, a named "
                        "guardian, or the institution.",
                explanation="Institutional costs are normally paid to the institution or supplier. Routing "
                            "them to an unrelated person's account is a strong diversion indicator.",
                values=values))
            break
    for start, end, sentence in sentences(ctx.case.story):
        solicits = _SOLICIT.search(sentence)
        if (solicits and (_PERSONAL_CHANNEL.search(sentence) or _DIRECT.search(sentence))) or _OFF_PLATFORM.search(sentence):
            findings.append(Finding(
                kind="payment_routing", code="OFF_PLATFORM_SOLICITATION", dimension="financial", component="semantic",
                severity=Severity.MATERIAL, confidence=0.8,
                summary="The campaign text asks donors to pay a private account or number instead of through the platform.",
                explanation="Donations made outside the platform cannot be tracked, refunded or tied to the "
                            "stated purpose, and bypass the payee named in the documents.",
                values=[campaign_value("campaign wording", " ".join(sentence.split())[:220])]))
            break
    return findings


def detect_implausible_cost(ctx: Context) -> List[Finding]:
    if "MEDICAL" not in ctx.case.category.upper():
        return []
    documented = sum(((s.total.value if s.total else (s.need or 0)) for s in summarize_costs(ctx)), Decimal(0))
    if documented and Decimal(str(ctx.case.goal_amount)) <= documented * (
            Decimal(1) + Decimal(str(ctx.config.amount_tolerance))):
        return []      # a high cost that the documents support is not suspicious
    benchmark = analyze_cost_benchmark(ctx.case.category, f"{ctx.case.title} {ctx.case.story}", ctx.case.goal_amount)
    if not benchmark or benchmark["benchmark_status"] != "SUSPICIOUSLY_EXCESSIVE":
        return []
    return [Finding(
        kind="plausibility", code="COST_ABOVE_TYPICAL_RANGE", dimension="narrative", component="semantic",
        severity=Severity.UNCERTAIN, confidence=0.4,
        summary="The requested amount is far above the typical range for this kind of treatment and no document supports it.",
        explanation="Unusually high costs can be genuine, so this is a request for an itemised estimate, not an accusation.",
        values=[campaign_value("requested amount", format_inr(ctx.case.goal_amount)),
                campaign_value("typical range", f"{format_inr(benchmark['typical_range_min'])} - "
                                                f"{format_inr(benchmark['typical_range_max'])}")])]


SIGNALS = [detect_settlement, detect_ineligibility, detect_unconfirmed, detect_payment_routing, detect_implausible_cost]
