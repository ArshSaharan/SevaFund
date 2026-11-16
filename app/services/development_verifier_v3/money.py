"""V3 context-aware money parsing with Decimal values and explicit currencies.

No exchange rates are inferred. A mention with malformed grouping is retained
as invalid evidence so the caller cannot silently treat a failed parse as zero.
"""
from decimal import Decimal, InvalidOperation
import re
from typing import List, Optional, Tuple

from pydantic import BaseModel

MAX_AMOUNT = Decimal("100000000000000")
_CURRENCIES = {
    "INR": "INR", "RS": "INR", "RUPEE": "INR", "RUPEES": "INR", "₹": "INR",
    "USD": "USD", "US$": "USD", "$": "USD", "DOLLAR": "USD", "DOLLARS": "USD",
    "GBP": "GBP", "£": "GBP", "POUND": "GBP", "POUNDS": "GBP",
    "EUR": "EUR", "€": "EUR", "EURO": "EUR", "EUROS": "EUR",
    "AUD": "AUD", "A$": "AUD", "CAD": "CAD", "C$": "CAD", "SGD": "SGD", "S$": "SGD",
    "AED": "AED", "CHF": "CHF", "JPY": "JPY", "NZD": "NZD", "ZAR": "ZAR",
}
_SCALES = {
    "thousand": Decimal(1000), "k": Decimal(1000), "lakh": Decimal(100000),
    "lakhs": Decimal(100000), "lac": Decimal(100000), "lacs": Decimal(100000),
    "crore": Decimal(10000000), "crores": Decimal(10000000), "cr": Decimal(10000000),
    "million": Decimal(1000000), "millions": Decimal(1000000),
    "billion": Decimal(1000000000), "billions": Decimal(1000000000),
}
_SCALE_RE = r"(?:thousand|lakhs?|lacs?|crores?|cr|millions?|billions?|k)"
_NUM_RE = r"\d(?:[\d.,]*\d)?"
_CURRENCY_ALT = r"US\$|A\$|C\$|S\$|INR|USD|GBP|EUR|AUD|CAD|SGD|AED|CHF|JPY|NZD|ZAR|rupees?|dollars?|pounds?|euros?|Rs\.?|₹|£|€|\$"
_PREFIX = re.compile(rf"(?<![A-Za-z0-9])(?P<currency>{_CURRENCY_ALT})(?![A-Za-z])\s*", re.I)
_NUMBER_WITH_SCALE = re.compile(rf"(?P<number>{_NUM_RE})\s*(?P<scale>{_SCALE_RE})?", re.I)
_SUFFIX = re.compile(r"\s*(?P<currency>rupees?|dollars?|pounds?|euros?|INR|USD|GBP|EUR|AUD|CAD|SGD|AED|CHF|JPY|NZD|ZAR)\b", re.I)
_BARE_FIELD = re.compile(rf"^\s*(?P<number>{_NUM_RE})\s*(?P<scale>{_SCALE_RE})?\s*(?:/-|only)?\s*$", re.I)
_MONEY_CONTEXT = re.compile(r"\b(amount|cost|fee|fees|tuition|estimate|invoice|bill|payable|due|total|budget|price|charge|charges|expenses?|quotation|arrears|balance|deposit|hospital|treatment|sanction|paid|received|remitted)\b", re.I)
_DATE_CONTEXT = re.compile(r"\b(date|dated|dob|birth|admission no|registration no|roll no|reference|ref\.?|uhid|invoice id|account|ward|page)\b", re.I)
_NONMONEY_AFTER = re.compile(r"\s*(?:students?|pupils?|famil(?:y|ies)|households?|books?|kits?|sets?|"
                             r"visits?|sessions?|weeks?|months?|years?|days?|beds?|rooms?|cases?|"
                             r"units?|devices?|beneficiaries|patients?)\b", re.I)
_NUMBER_WORDS = ("zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
                 "sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
                 "hundred|thousand|lakh|lac|million|crore|billion|and|point|half|quarter")
_WORD_AMOUNT = re.compile(rf"\b(?:{_NUMBER_WORDS})(?:[- ]+(?:{_NUMBER_WORDS})){{0,10}}\b", re.I)
_SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
          "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_WORD_SCALE = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lac": 100000,
               "million": 1000000, "crore": 10000000, "billion": 1000000000}


class MoneyMention(BaseModel):
    raw: str
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    start: int = 0
    end: int = 0
    valid: bool = True
    issue: Optional[str] = None
    role: str = "unspecified"

    @property
    def value(self) -> Optional[Decimal]:
        """Compatibility alias for V2 extraction code; currency remains explicit."""
        return self.amount


def _currency(token: Optional[str], default: Optional[str] = None) -> Optional[str]:
    if not token:
        return default
    key = re.sub(r"\s+", "", token).rstrip(".").upper()
    return _CURRENCIES.get(key, _CURRENCIES.get(token.upper(), default))


def _valid_grouping(integer: str, separator: str) -> bool:
    if separator == ",":
        return bool(re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3}", integer))
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{3})+", integer))


def _numeric_decimal(raw: str) -> Tuple[Optional[Decimal], Optional[str]]:
    token = raw.strip().replace(" ", "")
    if not token or not re.fullmatch(r"\d[\d.,]*", token):
        return None, "NOT_A_NUMBER"
    comma, dot = token.rfind(","), token.rfind(".")
    if comma >= 0 and dot >= 0:
        decimal_sep, grouping_sep = (",", ".") if comma > dot else (".", ",")
        whole, fraction = token.rsplit(decimal_sep, 1)
        if len(fraction) not in (1, 2):
            return None, "MALFORMED_DECIMAL"
        if grouping_sep in whole and not _valid_grouping(whole, grouping_sep):
            return None, "MALFORMED_GROUPING"
        normalized = whole.replace(grouping_sep, "") + "." + fraction
    elif comma >= 0:
        if _valid_grouping(token, ","):
            normalized = token.replace(",", "")
        else:
            whole, fraction = token.rsplit(",", 1)
            if len(fraction) in (1, 2) and whole.isdigit() and "," not in whole:
                normalized = whole + "." + fraction
            else:
                return None, "MALFORMED_GROUPING"
    elif dot >= 0:
        if token.count(".") > 1:
            return None, "MALFORMED_GROUPING"
        whole, fraction = token.split(".", 1)
        if not whole or not fraction:
            return None, "MALFORMED_DECIMAL"
        normalized = whole + "." + fraction
    else:
        normalized = token
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None, "NOT_A_NUMBER"
    if not amount.is_finite() or amount < 0:
        return None, "INVALID_AMOUNT"
    if amount > MAX_AMOUNT:
        return None, "OUT_OF_RANGE"
    return amount, None


def _words_decimal(text: str) -> Optional[Decimal]:
    tokens = re.findall(r"[a-z]+", text.lower())
    if not tokens or any(t not in _SMALL and t not in _TENS and t not in _WORD_SCALE and t not in {"and", "point", "half", "quarter"} for t in tokens):
        return None
    total, current, fraction = Decimal(0), Decimal(0), ""
    after_point = False
    try:
        for token in tokens:
            if token == "and":
                continue
            if token == "point":
                if after_point:
                    return None
                after_point = True
                continue
            if after_point:
                value = _SMALL.get(token)
                if value is None or value > 9:
                    return None
                fraction += str(value)
            elif token == "half":
                current += Decimal("0.5")
            elif token == "quarter":
                current += Decimal("0.25")
            elif token in _SMALL:
                current += _SMALL[token]
            elif token in _TENS:
                current += _TENS[token]
            elif token == "hundred":
                current = max(current, Decimal(1)) * 100
            else:
                scale = _WORD_SCALE[token]
                part = max(current, Decimal(1))
                if scale < 1000:
                    current = part * scale
                else:
                    total += part * scale
                    current = Decimal(0)
        result = total + current
        if fraction:
            result += Decimal("0." + fraction)
        return result
    except (KeyError, InvalidOperation):
        return None


def _scale(value: Decimal, scale: Optional[str]) -> Decimal:
    return value * _SCALES.get((scale or "").lower(), Decimal(1))


def _role(text: str, start: int) -> str:
    prefix = text[max(0, start - 70):start].lower()
    if re.search(r"paid|received|remitted|sanctioned|covered", prefix):
        return "paid_or_covered"
    if re.search(r"balance|outstanding|remaining", prefix):
        return "balance"
    if re.search(r"due|payable|arrears", prefix):
        return "due"
    if re.search(r"tuition|fee|fees", prefix):
        return "tuition_or_fee"
    if re.search(r"estimate|quotation|invoice|bill|cost|price|charge", prefix):
        return "estimated_cost"
    if re.search(r"goal|target|request|raising|budget", prefix):
        return "campaign_request"
    return "unspecified"


def _make(raw: str, number: str, currency: Optional[str], start: int, end: int,
          scale: Optional[str] = None, role: str = "unspecified") -> MoneyMention:
    amount, issue = _numeric_decimal(number)
    if amount is None:
        return MoneyMention(raw=raw, currency=currency, start=start, end=end, valid=False, issue=issue, role=role)
    amount = _scale(amount, scale)
    if amount > MAX_AMOUNT:
        return MoneyMention(raw=raw, currency=currency, start=start, end=end, valid=False, issue="OUT_OF_RANGE", role=role)
    return MoneyMention(raw=raw, amount=amount, currency=currency, start=start, end=end, role=role)


def find_amounts(text: str, default_currency: Optional[str] = "INR") -> List[MoneyMention]:
    """Extract currency-tagged values or financially contextual bare values."""
    text = text or ""
    mentions: List[MoneyMention] = []
    occupied = []

    for marker in _PREFIX.finditer(text):
        tail = text[marker.end():]
        number = _NUMBER_WITH_SCALE.match(tail)
        currency = _currency(marker.group("currency"), default_currency)
        if number:
            end = marker.end() + number.end()
            mentions.append(_make(text[marker.start():end], number.group("number"), currency,
                                  marker.start(), end, number.group("scale"), _role(text, marker.start())))
            occupied.append((marker.start(), end))
            continue
        word = _WORD_AMOUNT.match(tail.lstrip())
        if word:
            offset = marker.end() + (len(tail) - len(tail.lstrip()))
            amount = _words_decimal(word.group(0))
            end = offset + word.end()
            raw = text[marker.start():end]
            if amount is None:
                mentions.append(MoneyMention(raw=raw, currency=currency, start=marker.start(), end=end,
                                              valid=False, issue="MALFORMED_WRITTEN_AMOUNT"))
            else:
                mentions.append(MoneyMention(raw=raw, amount=amount, currency=currency, start=marker.start(), end=end,
                                              role=_role(text, marker.start())))
            occupied.append((marker.start(), end))

    for suffix in _SUFFIX.finditer(text):
        before = text[:suffix.start()]
        words = list(_WORD_AMOUNT.finditer(before))
        if words:
            word = words[-1]
            # A scale token in "2.4 crore rupees" is not a written number.
            is_scale_after_digits = bool(re.search(r"\d[\d.,]*\s*$", before[:word.start()]))
            if not is_scale_after_digits and not any(word.start() < end and start < suffix.end() for start, end in occupied):
                amount = _words_decimal(word.group(0))
                currency = _currency(suffix.group("currency"), default_currency)
                if amount is None:
                    mentions.append(MoneyMention(raw=text[word.start():suffix.end()], currency=currency,
                                                  start=word.start(), end=suffix.end(), valid=False,
                                                  issue="MALFORMED_WRITTEN_AMOUNT"))
                else:
                    mentions.append(MoneyMention(raw=text[word.start():suffix.end()], amount=amount, currency=currency,
                                                  start=word.start(), end=suffix.end(), role=_role(text, word.start())))
                occupied.append((word.start(), suffix.end()))
                continue
        number = re.search(rf"(?P<number>{_NUM_RE})\s*(?P<scale>{_SCALE_RE})?\s*$", before, re.I)
        if number and not any(number.start() < end and start < suffix.end() for start, end in occupied):
            currency = _currency(suffix.group("currency"), default_currency)
            mentions.append(_make(text[number.start():suffix.end()], number.group("number"), currency,
                                  number.start(), suffix.end(), number.group("scale"), _role(text, number.start())))
            occupied.append((number.start(), suffix.end()))

    for match in _NUMBER_WITH_SCALE.finditer(text):
        if any(match.start() < end and start < match.end() for start, end in occupied):
            continue
        prefix = text[max(0, match.start() - 70):match.start()]
        suffix = text[match.end():match.end() + 25]
        scale = match.group("scale")
        identifier_code = bool(re.search(r"\b[A-Z]{1,6}[-/]\s*$", prefix))
        if not scale and (not _MONEY_CONTEXT.search(prefix) or _DATE_CONTEXT.search(prefix[-35:])):
            continue
        if not scale and identifier_code:
            continue
        if not scale and _NONMONEY_AFTER.match(suffix):
            continue
        if not scale and re.match(r"\s*(?:/|[-]\d|\d)", suffix):
            continue
        currency = "INR" if scale or _MONEY_CONTEXT.search(prefix) else default_currency
        mentions.append(_make(match.group(0), match.group("number"), currency,
                              match.start(), match.end(), scale, _role(text, match.start())))
        occupied.append((match.start(), match.end()))
    return sorted(mentions, key=lambda item: item.start)


def parse_amount_field(value: str, currency_context: Optional[str] = None) -> MoneyMention:
    """Parse a known money field; a bare number needs an explicit label."""
    raw = (value or "").strip()
    if not raw:
        return MoneyMention(raw=raw, valid=False, issue="EMPTY_AMOUNT")
    mentions = find_amounts(raw, default_currency=None)
    if len(mentions) == 1:
        return mentions[0]
    if len(mentions) > 1:
        return MoneyMention(raw=raw, valid=False, issue="AMBIGUOUS_AMOUNT")
    marker = _PREFIX.match(raw)
    if marker:
        return MoneyMention(raw=raw, currency=_currency(marker.group("currency")), valid=False,
                            issue="MALFORMED_AMOUNT")
    bare = _BARE_FIELD.fullmatch(raw)
    if bare:
        if not currency_context or not _MONEY_CONTEXT.search(currency_context):
            return MoneyMention(raw=raw, valid=False, issue="CURRENCY_CONTEXT_REQUIRED")
        return _make(raw, bare.group("number"), "INR", 0, len(raw), bare.group("scale"),
                     _role(currency_context, len(currency_context)))
    return MoneyMention(raw=raw, valid=False, issue="NOT_A_MONETARY_FIELD")


def compare_amounts(left: MoneyMention, right: MoneyMention) -> Optional[Decimal]:
    """Return left minus right only for valid, currency-matched amounts."""
    if not left.valid or not right.valid or left.amount is None or right.amount is None:
        return None
    if not left.currency or left.currency != right.currency:
        return None
    return left.amount - right.amount


def format_inr(amount) -> str:
    digits = f"{int(Decimal(str(amount)).quantize(Decimal('1')))}"
    if len(digits) <= 3:
        return f"₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])
