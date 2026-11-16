"""Cross-source checks for explicit duration and quantity facts.

These checks compare values tied to the same unit across the campaign and a
readable upload. They do not treat a keyword or a standalone number as fraud.
"""
import re
from decimal import Decimal
from typing import Dict, List, Tuple

from .consistency import Context, campaign_value
from .schemas import Finding, FindingValue, Severity

_NUM_WORDS = ("zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
              "sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred")
_NUMBER = rf"(?:\d[\d,]*|{_NUM_WORDS})(?:[- ]+(?:{_NUM_WORDS})){{0,2}}"
_DURATION = re.compile(rf"\b(?P<number>{_NUMBER})(?:\s+[a-z-]+){{0,2}}?\s+(?P<unit>days?|weeks?|months?|years?)\b", re.I)
_QUANTITY = re.compile(rf"\b(?P<number>{_NUMBER})(?:\s+[a-z-]+){{0,2}}?\s+(?P<unit>books?|titles?|kits?|sets?|seats?|students?|pupils?|"
                       r"families|households?|meals?|beds?|devices?|machines?|tanks?|classrooms?|sessions?|"
                       r"bursaries|scholarships?|tablets?|uniforms?|wheelchairs?|patients?|beneficiaries|"
                       r"stalls?|frames?|panels?|cisterns?|heaters?|alarms?|seedlings?|crates?|bundles?|"
                       r"handrails?|steps?|locks?|doors?|water points?|solar lamps?|shelters?)\b", re.I)
_WORD_VALUES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
                "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
                "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
                "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100}


def _number(value: str) -> Decimal:
    normalized = value.casefold().replace("-", " ").replace(",", " ")
    if normalized.replace(" ", "").isdigit():
        return Decimal(normalized.replace(" ", ""))
    total = 0
    for token in normalized.split():
        number = _WORD_VALUES[token]
        total = total * number if token == "hundred" else total + number
    return Decimal(total)


def _facts(text: str, pattern: re.Pattern, unit_groups: Dict[str, str]) -> List[Tuple[Decimal, str, str]]:
    facts = []
    for match in pattern.finditer(text or ""):
        unit = match.group("unit").casefold()
        base = unit_groups.get(unit, unit.rstrip("s"))
        facts.append((_number(match.group("number")), base, match.group(0)))
    return facts


_DAY_SCALE = {"day": Decimal(1), "week": Decimal(7), "month": Decimal(30), "year": Decimal(365)}
_DURATION_UNITS = {unit: unit for unit in _DAY_SCALE}
_QUANTITY_UNITS = {word: word.rstrip("s") for word in (
    "book books title titles kit kits set sets seat seats student students pupil pupils family families household"
    " households meal meals bed beds device devices machine machines tank tanks classroom classrooms session"
    " sessions bursary bursaries scholarship scholarships tablet tablets uniform uniforms wheelchair wheelchairs"
    " patient patients beneficiary beneficiaries stall stalls frame frames panel panels cistern cisterns heater heaters"
    " alarm alarms seedling seedlings crate crates bundle bundles handrail handrails step steps lock locks door doors"
    " shelter shelters water-point water-points solar-lamp solar-lamps").split()}


def check_duration_consistency(ctx: Context) -> List[Finding]:
    claim = f"{ctx.case.title}. {ctx.case.story}"
    claimed = _facts(claim, _DURATION, _DURATION_UNITS)
    findings = []
    for doc in ctx.docs:
        actual = _facts(ctx.texts.get(doc.index, ""), _DURATION, _DURATION_UNITS)
        for requested, _, requested_raw in claimed:
            expected_days = requested * _DAY_SCALE[_facts_unit(requested_raw)]
            candidate_values = [(value * _DAY_SCALE[unit], value, unit, raw) for value, unit, raw in actual]
            if not candidate_values:
                continue
            # Pick the closest directly documented duration; if several values
            # appear, do not accuse when one agrees with the campaign.
            closest = min(candidate_values, key=lambda item: abs(item[0] - expected_days))
            documented_days, documented, unit, documented_raw = closest
            diff = abs(documented_days - expected_days)
            larger, smaller = max(documented_days, expected_days), min(documented_days, expected_days)
            ratio = larger / max(smaller, Decimal(1))
            explicit_limit = bool(re.search(r"no (?:later|further|additional)|only|ends? after|ends? in", ctx.texts.get(doc.index, ""), re.I))
            if ratio < Decimal("2.2") or diff < Decimal(30) or not explicit_limit:
                continue
            severity = Severity.MATERIAL
            findings.append(Finding(
                kind="duration", code="CAMPAIGN_DOCUMENT_DURATION_CONFLICT", dimension="narrative",
                component="cross_document", severity=severity, confidence=0.78,
                summary=f"The campaign describes {requested_raw}, while '{doc.title}' records {documented_raw} and states that no additional period is scheduled.",
                explanation="The stated funding period is substantially longer than the schedule in the uploaded record. The period and whether further instruction is planned need review.",
                values=[campaign_value("campaign period", requested_raw),
                        FindingValue(field="documented period", value=documented_raw, document=doc.title,
                                     doc_index=doc.index)]))
            break
    return findings


def _facts_unit(raw: str) -> str:
    match = re.search(r"(days?|weeks?|months?|years?)\b", raw, re.I)
    return match.group(1).casefold().rstrip("s")


def check_quantity_consistency(ctx: Context) -> List[Finding]:
    claim = f"{ctx.case.title}. {ctx.case.story}"
    requested = _facts(claim, _QUANTITY, _QUANTITY_UNITS)
    findings = []
    for doc in ctx.docs:
        actual = _facts(ctx.texts.get(doc.index, ""), _QUANTITY, _QUANTITY_UNITS)
        for count, unit, raw in requested:
            matches = [(value, text) for value, doc_unit, text in actual if doc_unit == unit]
            if not matches:
                continue
            closest = min(matches, key=lambda item: abs(item[0] - count))
            value, doc_raw = closest
            if value == count or max(value, count) < min(value, count) * Decimal("1.5"):
                continue
            findings.append(Finding(
                kind="quantity", code="CAMPAIGN_DOCUMENT_QUANTITY_CONFLICT", dimension="financial",
                component="cross_document", severity=Severity.MATERIAL, confidence=0.72,
                summary=f"The campaign requests {raw}, but '{doc.title}' records {doc_raw}.",
                explanation="The quantities stated in the request and the supporting document differ substantially; confirm which figure is current.",
                values=[campaign_value("requested quantity", raw),
                        FindingValue(field="documented quantity", value=doc_raw, document=doc.title,
                                     doc_index=doc.index)]))
            break
    return findings
