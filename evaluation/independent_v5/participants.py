"""Pseudonymous participant registry and independence rules (standard library only).

The coordinator keeps the mapping from codes to real people outside the repository.  Authors, labellers and
adjudicators must have declared independence and answered 'no' to every involvement question; the developer and
the AI assistant are excluded by reserved identity.  One role per person."""
import csv
import re
from pathlib import Path
from typing import List, Optional

FIELDS = ["participant_id", "role", "independence_declared", "involved_in_implementation",
          "involved_in_prior_benchmarks_or_tuning", "saw_verifier_code_or_lexicons", "saw_prior_corpora",
          "declared_on", "notes"]
INVOLVEMENT = ["involved_in_implementation", "involved_in_prior_benchmarks_or_tuning", "saw_verifier_code_or_lexicons",
               "saw_prior_corpora"]
ROLES = {"author", "labeller", "adjudicator", "coordinator"}
RESERVED_EXCLUDED = {"DEV", "DEVELOPER", "CLAUDE", "ASSISTANT", "AI", "LLM"}


def load(path: Path) -> dict:
    errors, rows = [], {}
    with Path(path).open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [f for f in FIELDS if f not in (reader.fieldnames or [])]
        if missing:
            return {"participants": {}, "errors": [f"participant registry is missing columns {missing}"]}
        for row in reader:
            pid = (row["participant_id"] or "").strip()
            if not re.fullmatch(r"[A-Z0-9-]{2,24}", pid):
                errors.append(f"participant_id '{pid}' must be a pseudonymous code (A-Z, 0-9, -)")
                continue
            if pid in rows:
                errors.append(f"participant {pid} appears twice (one role per person)")
                continue
            if row["role"] not in ROLES:
                errors.append(f"{pid}: role must be one of {sorted(ROLES)}")
            rows[pid] = row
    return {"participants": rows, "errors": errors}


def eligible(row: Optional[dict], role: str) -> List[str]:
    """Reasons a registered participant may not act in `role` (empty list = eligible)."""
    if row is None:
        return ["not in the participant registry"]
    reasons = []
    pid = row["participant_id"].upper()
    if pid in RESERVED_EXCLUDED or any(pid.endswith(f"-{r}") for r in RESERVED_EXCLUDED):
        reasons.append("reserved identity (developer or AI assistant) is excluded")
    if row["role"] != role:
        reasons.append(f"registered as {row['role']}, not {role}")
    if role != "coordinator":
        if (row["independence_declared"] or "").strip().lower() != "yes":
            reasons.append("no signed independence declaration")
        for field in INVOLVEMENT:
            if (row[field] or "").strip().lower() != "no":
                reasons.append(f"{field} is not 'no'")
    return reasons


def summary(registry: dict) -> dict:
    rows = registry["participants"].values()
    by_role = {}
    for role in sorted(ROLES):
        members = [r for r in rows if r["role"] == role]
        by_role[role] = {"registered": len(members), "eligible": sum(not eligible(r, role) for r in members)}
    return by_role
