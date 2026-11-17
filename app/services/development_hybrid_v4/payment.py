"""Payment-account consistency (hybrid v4, development only).

Substituted bank details are a common way to divert funds raised for a genuine need: a real bill or letter is
edited so that the payment goes to someone else's account.  This check compares the bank details written in the
uploaded documents, pairing each account number with the account holder named closest to it:

  PAYMENT_ACCOUNT_CONFLICT  the same account holder is given different account numbers in different documents, or
                            the same account number is given to different account holders.

A conflict sends the campaign to manual review (never rejection).  A payee who is neither the beneficiary nor the
institution is already detected by frozen V3 (THIRD_PARTY_PAYEE).  Whatever the documents say, the payment
destination must still be confirmed independently before activation.
"""
import re
from typing import Dict, List, Set, Tuple

from pydantic import BaseModel, Field

from .config import SETTINGS

_ACCOUNT = re.compile(r"\b(?:a/c|acct|account)\.?\s*(?:no\.?|number|num|#)?\s*[:.\-]?\s*(\d[\d \-]{6,26}\d)", re.I)
_HOLDER = re.compile(r"\b(?:account\s+holder(?:'s)?(?:\s+name)?|account\s+name|a/c\s+(?:holder|name)|payee(?:\s+name)?|"
                     r"in\s+favou?r\s+of|payable\s+to|beneficiary\s+name)\s*[:\-]?\s*"
                     r"([A-Za-z][A-Za-z.&'\- ]{1,70}?)(?=\s*(?:[,;\n(]|\.\s|\.$|$|\s+(?:a/c|acct|account|bank|ifsc|branch)\b))",
                     re.I)
_DROP = {"the", "of", "a", "c", "and", "account", "ltd", "limited", "pvt", "private", "mr", "mrs", "ms", "smt", "shri",
         "sri", "dr", "m", "s"}


class PaymentFinding(BaseModel):
    code: str = "PAYMENT_ACCOUNT_CONFLICT"
    summary: str
    evidence: List[Dict[str, str]] = Field(default_factory=list)     # [{"document": ..., "quote": ...}]


def _holder_key(name: str) -> frozenset:
    return frozenset(t for t in re.findall(r"[a-z]+", name.casefold()) if t not in _DROP)


def _same_holder(a: frozenset, b: frozenset) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return len(small) >= 2 and small <= large


def accounts(documents: List[dict]) -> List[Tuple[str, str, str, frozenset, str]]:
    """(document title, account digits, holder as written, holder key, quote) for every account number found."""
    minimum = SETTINGS["payment_account_min_digits"]
    found = []
    for doc in documents:
        text = doc.get("content", "") or ""
        holders = [(m.start(), m.group(1).strip(" .-")) for m in _HOLDER.finditer(text)]
        for match in _ACCOUNT.finditer(text):
            digits = re.sub(r"\D", "", match.group(1))
            if len(digits) < minimum or not holders:
                continue
            position, holder = min(holders, key=lambda h: abs(h[0] - match.start()))
            start = min(match.start(), position)                  # from the holder label (or the account) onwards
            quote = " ".join(text[start:match.end()].split())
            found.append((doc.get("title", ""), digits, holder, _holder_key(holder), quote))
    return found


def check(case: dict) -> List[PaymentFinding]:
    rows = accounts(case.get("documents", []))
    findings: List[PaymentFinding] = []
    reported: Set[Tuple[str, str]] = set()
    for i, (doc_a, acc_a, holder_a, key_a, quote_a) in enumerate(rows):
        for doc_b, acc_b, holder_b, key_b, quote_b in rows[i + 1:]:
            if doc_a == doc_b:
                continue
            same_holder = _same_holder(key_a, key_b)
            if same_holder and acc_a != acc_b:
                summary = (f"'{holder_a}' is given account {acc_a} in '{doc_a}' but account {acc_b} in '{doc_b}'.")
            elif acc_a == acc_b and not same_holder and key_a and key_b:
                summary = (f"Account {acc_a} is held by '{holder_a}' in '{doc_a}' but by '{holder_b}' in '{doc_b}'.")
            else:
                continue
            pair = tuple(sorted((f"{doc_a}|{acc_a}", f"{doc_b}|{acc_b}")))
            if pair in reported:
                continue
            reported.add(pair)
            findings.append(PaymentFinding(summary=summary, evidence=[{"document": doc_a, "quote": quote_a},
                                                                      {"document": doc_b, "quote": quote_b}]))
    return findings
