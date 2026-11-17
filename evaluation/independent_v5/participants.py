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


def _hours(row: dict) -> float:
    try:
        return float((row.get("committed_hours") or "0").strip() or 0)
    except ValueError:
        return 0.0


def feasibility(registry: dict, staffing: dict) -> dict:
    """Whether eligible, registered participants' committed hours cover each design (plus the buffer).

    `committed_hours` is an optional registry column; a missing value counts as 0.  The design is chosen only after
    this check, and the sample size is never reduced without the owner's approval."""
    rows = list(registry["participants"].values())
    eligible_rows = {role: [r for r in rows if r["role"] == role and not eligible(r, role)] for role in ROLES}
    buffer = 1 + staffing["buffer"]
    out = {"eligible_counts": {role: len(v) for role, v in eligible_rows.items()},
           "committed_hours": {role: sum(_hours(r) for r in v) for role, v in eligible_rows.items()}, "designs": {}}
    for design, hours in staffing["hours_by_design"].items():
        shortfalls = []
        if len(eligible_rows["author"]) < 3:
            shortfalls.append(f"{len(eligible_rows['author'])} eligible authors (minimum 3)")
        need = hours["authoring"] * buffer
        if out["committed_hours"]["author"] < need:
            shortfalls.append(f"authors commit {out['committed_hours']['author']:g} h of {need:.0f} h needed")
        labellers = sorted(_hours(r) for r in eligible_rows["labeller"])[-2:]
        per_labeller = hours["labelling_total"] / 2 * buffer
        if len(labellers) < 2 or min(labellers) < per_labeller:
            shortfalls.append(f"needs 2 eligible labellers with {per_labeller:.0f} h each (have {labellers})")
        for role, key in (("adjudicator", "adjudication"), ("coordinator", "coordination")):
            need = hours[key] * buffer
            if not eligible_rows[role] or max(_hours(r) for r in eligible_rows[role]) < need:
                shortfalls.append(f"needs an eligible {role} with {need:.0f} h")
        out["designs"][design] = {"feasible": not shortfalls, "shortfalls": shortfalls}
    return out
