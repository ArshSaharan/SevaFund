"""Blind labelling: sheet checks, agreement, adjudication and sealing (standard library only).

Never reads any system output.  The adjudicated file is the only label source the scorer accepts."""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .participants import eligible

SHEET_FIELDS = ["case_id", "labeller_id", "truth_label", "documentation", "missing_items", "detectable_from_dossier",
                "detectable_by_external_confirmation", "decisive_evidence_titles", "justified_amount_inr",
                "acceptable_end_states", "date_check", "notes"]
ADJUDICATION_FIELDS = ["case_id", "field", "labeller_a_value", "labeller_b_value", "adjudicated_value",
                       "adjudicator_id", "reason"]
FINAL_FIELDS = ["case_id", "truth_label", "documentation", "missing_items", "detectable_from_dossier",
                "detectable_by_external_confirmation", "decisive_evidence_titles", "justified_amount_inr",
                "acceptable_end_states", "date_check", "adjudication_status", "notes"]
COMPARED = ["truth_label", "documentation", "missing_items", "detectable_from_dossier",
            "detectable_by_external_confirmation", "acceptable_end_states", "date_check"]
MISSING_ITEMS = {"ID", "NEED", "COST", "PAYEE"}
END_STATES = {"APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW"}
YES_NO = {"yes", "no"}
DATE_CHECK = {"consistent", "inconsistent", "n/a"}


def _set(value: str) -> frozenset:
    return frozenset(v.strip() for v in (value or "").split(";") if v.strip())


def read_sheet(path: Path) -> List[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_sheet(path: Path, case_ids: List[str], participants: Optional[dict] = None,
                authors: Optional[set] = None) -> dict:
    rows, errors = read_sheet(path), []
    if rows and set(SHEET_FIELDS) - set(rows[0]):
        return {"valid": False, "errors": [f"missing columns {sorted(set(SHEET_FIELDS) - set(rows[0]))}"], "rows": 0}
    seen = Counter(r["case_id"] for r in rows)
    errors += [f"{cid}: labelled {n} times" for cid, n in seen.items() if n > 1]
    errors += [f"{cid}: not labelled" for cid in sorted(set(case_ids) - set(seen))]
    errors += [f"{cid}: not in the submission" for cid in sorted(set(seen) - set(case_ids))]
    labellers = {r["labeller_id"] for r in rows}
    if len(labellers) != 1:
        errors.append(f"a sheet must come from exactly one labeller, found {sorted(labellers)}")
    for r in rows:
        cid = r["case_id"]
        if r["truth_label"] not in config.LABELS:
            errors.append(f"{cid}: truth_label must be one of {list(config.LABELS)}")
        if r["documentation"] not in config.DOCUMENTATION:
            errors.append(f"{cid}: documentation must be complete or incomplete")
        missing = _set(r["missing_items"])
        if missing - MISSING_ITEMS:
            errors.append(f"{cid}: missing_items must use {sorted(MISSING_ITEMS)}")
        if (r["documentation"] == "incomplete") != bool(missing):
            errors.append(f"{cid}: incomplete documentation must name missing items, and complete must name none")
        for field in ("detectable_from_dossier", "detectable_by_external_confirmation"):
            if r["truth_label"] == "fraudulent" and r[field] not in YES_NO:
                errors.append(f"{cid}: {field} must be yes or no for fraud")
        states = _set(r["acceptable_end_states"])
        if not states or states - END_STATES:
            errors.append(f"{cid}: acceptable_end_states must be a non-empty subset of {sorted(END_STATES)}")
        if "APPROVED" in states and (r["truth_label"] != "legitimate" or r["documentation"] == "incomplete"):
            errors.append(f"{cid}: APPROVED is acceptable only for legitimate, complete cases")
        if r["date_check"] not in DATE_CHECK:
            errors.append(f"{cid}: date_check must be one of {sorted(DATE_CHECK)}")
        amount = (r["justified_amount_inr"] or "").strip()
        if amount and not amount.replace(".", "", 1).isdigit():
            errors.append(f"{cid}: justified_amount_inr must be a number or blank")
    if participants is not None:
        for labeller in labellers:
            errors += [f"labeller {labeller}: {r}" for r in eligible(participants.get(labeller), "labeller")]
            if authors and labeller in authors:
                errors.append(f"labeller {labeller} also authored cases")
    return {"valid": not errors, "errors": errors, "rows": len(rows), "labeller": sorted(labellers)}


def kappa(a: Dict[str, str], b: Dict[str, str]) -> Optional[float]:
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    observed = sum(a[i] == b[i] for i in shared) / len(shared)
    categories = {a[i] for i in shared} | {b[i] for i in shared}
    expected = sum((sum(a[i] == c for i in shared) / len(shared)) * (sum(b[i] == c for i in shared) / len(shared))
                   for c in categories)
    return 1.0 if expected == 1 else round((observed - expected) / (1 - expected), 4)


def agreement(sheet_a: Path, sheet_b: Path) -> dict:
    a = {r["case_id"]: r for r in read_sheet(sheet_a)}
    b = {r["case_id"]: r for r in read_sheet(sheet_b)}
    la, lb = {r["labeller_id"] for r in a.values()}, {r["labeller_id"] for r in b.values()}
    disagreements = []
    for cid in sorted(set(a) & set(b)):
        for field in COMPARED:
            va, vb = a[cid][field], b[cid][field]
            same = _set(va) == _set(vb) if field in ("missing_items", "acceptable_end_states") else va == vb
            if not same:
                disagreements.append({"case_id": cid, "field": field, "labeller_a_value": va, "labeller_b_value": vb})
    return {"labellers": [sorted(la), sorted(lb)], "same_labeller_on_both_sheets": bool(la & lb),
            "cases": len(set(a) & set(b)),
            "kappa_truth_label": kappa({k: v["truth_label"] for k, v in a.items()}, {k: v["truth_label"] for k, v in b.items()}),
            "kappa_documentation": kappa({k: v["documentation"] for k, v in a.items()},
                                         {k: v["documentation"] for k, v in b.items()}),
            "kappa_date_check": kappa({k: v["date_check"] for k, v in a.items()}, {k: v["date_check"] for k, v in b.items()}),
            "disagreements": disagreements,
            "cases_with_disagreement": sorted({d["case_id"] for d in disagreements})}


def adjudication_template(sheet_a: Path, sheet_b: Path, out: Path) -> int:
    if Path(out).exists():
        raise SystemExit(f"{out} exists")
    rows = agreement(sheet_a, sheet_b)["disagreements"]
    with Path(out).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "adjudicated_value": "", "adjudicator_id": "", "reason": ""})
    return len(rows)


def merge(sheet_a: Path, sheet_b: Path, adjudication: Optional[Path], out: Path,
          participants: Optional[dict] = None) -> dict:
    """Agreed fields are taken as is; every disagreement needs an adjudicated value from a third person.  A truth or
    documentation disagreement left unresolved makes the case `borderline` / unresolved, listed in the log."""
    if Path(out).exists():
        raise SystemExit(f"{out} exists; adjudicated labels are never overwritten")
    a = {r["case_id"]: r for r in read_sheet(sheet_a)}
    b = {r["case_id"]: r for r in read_sheet(sheet_b)}
    report = agreement(sheet_a, sheet_b)
    if report["same_labeller_on_both_sheets"]:
        raise SystemExit("both sheets come from the same labeller")
    decided, errors = {}, []
    labellers = set(report["labellers"][0]) | set(report["labellers"][1])
    if adjudication is not None:
        for row in read_sheet(adjudication):
            if not row["adjudicated_value"].strip():
                continue                                    # left blank: not adjudicated
            if row["adjudicated_value"].strip() == "-":
                row = {**row, "adjudicated_value": ""}      # '-' records an adjudicated empty value
            if row["adjudicator_id"] in labellers:
                errors.append(f"{row['case_id']}: the adjudicator must not be one of the two labellers")
            if participants is not None:
                    errors += [f"adjudicator {row['adjudicator_id']}: {r}"
                           for r in eligible(participants.get(row["adjudicator_id"]), "adjudicator")]
            decided[(row["case_id"], row["field"])] = row
    if errors:
        raise SystemExit("Adjudication rejected:\n- " + "\n- ".join(sorted(set(errors))))
    disagreement = {(d["case_id"], d["field"]) for d in report["disagreements"]}
    final, log = [], []
    for cid in sorted(a):
        row = {k: a[cid][k] for k in FINAL_FIELDS if k in a[cid]}
        status = "agreed"
        for field in COMPARED + ["decisive_evidence_titles", "justified_amount_inr"]:
            if (cid, field) in disagreement:
                if (cid, field) in decided:
                    row[field] = decided[(cid, field)]["adjudicated_value"]
                    status = "adjudicated"
                    log.append({**decided[(cid, field)], "outcome": "adjudicated"})
                else:
                    log.append({"case_id": cid, "field": field, "outcome": "unresolved"})
                    if field in ("truth_label", "documentation"):
                        status = "unresolved"
        if status == "unresolved":
            row["truth_label"] = "borderline"
            row["acceptable_end_states"] = "NEEDS_MORE_INFORMATION;FLAG_FOR_REVIEW"
        elif a[cid]["decisive_evidence_titles"] != b[cid]["decisive_evidence_titles"] and (cid, "decisive_evidence_titles") not in decided:
            row["decisive_evidence_titles"] = ";".join(sorted(_set(a[cid]["decisive_evidence_titles"]) | _set(b[cid]["decisive_evidence_titles"])))
        row["adjudication_status"] = status
        row["notes"] = " | ".join(x for x in (a[cid]["notes"], b[cid]["notes"]) if x)
        final.append(row)
    with Path(out).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_FIELDS)
        writer.writeheader()
        writer.writerows(final)
    log_path = Path(out).with_suffix(".adjudication_log.json")
    log_path.write_text(json.dumps({"agreement": {k: v for k, v in report.items() if k != "disagreements"},
                                    "disagreements": report["disagreements"], "decisions": log}, indent=2) + "\n",
                        encoding="utf-8")
    return {"cases": len(final), "status": dict(Counter(r["adjudication_status"] for r in final)),
            "kappa_truth_label": report["kappa_truth_label"], "kappa_documentation": report["kappa_documentation"],
            "log": str(log_path)}


def read_final(path: Path) -> Dict[str, dict]:
    rows = read_sheet(path)
    if rows and set(FINAL_FIELDS) - set(rows[0]):
        raise SystemExit(f"adjudicated label file is missing columns {sorted(set(FINAL_FIELDS) - set(rows[0]))}")
    return {r["case_id"]: r for r in rows}


def seal(final: Path, out: Path, agreement_report: dict) -> dict:
    if Path(out).exists():
        raise SystemExit(f"{out} exists; a label seal is never overwritten")
    rows = read_final(final)
    record = {"sha256": config.sha256_file(final), "cases": len(rows),
              "status": dict(Counter(r["adjudication_status"] for r in rows.values())),
              "kappa_truth_label": agreement_report.get("kappa_truth_label"),
              "kappa_documentation": agreement_report.get("kappa_documentation"),
              "kappa_date_check": agreement_report.get("kappa_date_check"),
              "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
              "rule": "Sealed before any system output exists. Never changed after results are seen."}
    Path(out).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record
