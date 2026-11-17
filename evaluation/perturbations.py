"""Deterministic, meaning-preserving perturbations of case documents.

Used to measure whether a verifier's decision is stable under harmless
formatting changes it was not developed against.  None of these changes alter
a fact: amounts, dates, names and layout are only re-expressed.
"""
import re
from datetime import date

_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]
_MONTH_INDEX = {name.lower()[:3]: i + 1 for i, name in enumerate(_MONTHS)}


def currency_style(text: str, case: dict) -> str:
    """₹1,23,000 -> Rs. 1,23,000/-  and  ₹1.27 lakh -> Rs. 1.27 lakh  and
    Rs. 1,23,000/- / INR 1,23,000.00 / Rs 123000 -> ₹1,23,000.

    Fixed after the first two frozen runs: earlier versions rewrote "₹1.27 lakh"
    as "Rs. 1/-.27 lakh" and "₹3,65,000." as "Rs. 3,65/-,000.", which changed the
    amounts (not meaning-preserving).  tests/test_development_dataset_v2.py now
    checks that every perturbation preserves every parsed rupee amount."""
    text = re.sub(r"Rs\.?\s?(\d[\d,]*(?:\.\d+)?)(?:/-)?", r"__RUPEE__\1", text)
    text = re.sub(r"INR (\d[\d,]*)\.00", r"__RUPEE__\1", text)
    text = re.sub(r"₹(\d[\d,]*(?:\.\d+)?)(\s+(?:lakh|crore)s?)", r"Rs. \1\2", text)
    # The number must be taken whole: never stop inside "3,65,000" (a sentence-final
    # full stop is not a decimal point).
    text = re.sub(r"₹(\d(?:[\d,]*\d)?(?:\.\d+)?)(?![\d,]|\.\d)", r"Rs. \1/-", text)
    return text.replace("__RUPEE__", "₹")


def date_style(text: str, case: dict) -> str:
    """Numeric day-first dates -> '7 March 2026'; written dates -> 07/03/2026."""
    def numeric(match):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            date(year, month, day)
        except ValueError:
            return match.group(0)
        return f"{day} {_MONTHS[month - 1]} {year}"

    def written(match):
        day, month, year = int(match.group(1)), _MONTH_INDEX[match.group(2).lower()[:3]], int(match.group(3))
        return f"{day:02d}/{month:02d}/{year}"

    swapped = re.sub(r"(?<![\w/])(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b",
                     lambda m: "@@" + written(m) + "@@", text)
    swapped = re.sub(r"(?<![\w/@])(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?![\w@])", numeric, swapped)
    return swapped.replace("@@", "")


def name_style(text: str, case: dict) -> str:
    """'Asha Kumari Verma' -> 'VERMA, ASHA KUMARI' wherever the beneficiary is named."""
    name = case["input"].get("beneficiary_name") or ""
    parts = name.split()
    if case["input"].get("beneficiary_type", "SELF") != "SELF" or len(parts) < 2:
        return text
    return text.replace(name, f"{parts[-1].upper()}, {' '.join(parts[:-1]).upper()}")


def layout_collapse(text: str, case: dict) -> str:
    """Collapse table alignment and dotted leaders, as OCR output often does."""
    text = re.sub(r"\s*\.{3,}\s*", " ", text)
    return re.sub(r"[ \t]{2,}", " ", text)


PERTURBATIONS = {"currency_style": currency_style, "date_style": date_style, "name_style": name_style,
                 "layout_collapse": layout_collapse}


def perturb_case(case: dict, kind: str) -> dict:
    function = PERTURBATIONS[kind]
    data = dict(case["input"])
    data["documents"] = [dict(d, content=function(d["content"], case)) for d in data.get("documents", [])]
    return dict(case, input=data)
