"""Coordinator tools for the v4 independent test set (see independent_test_protocol_v4.md).

    validate   check an authored .jsonl against the protocol; write a sealed manifest if it passes
    agreement  Cohen's kappa between two labelling sheets (before adjudication)

The validator never runs a verifier and never reads labels from a verifier.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CATEGORIES = {"MEDICAL", "EDUCATION", "COMMUNITY"}
LABELS = {"legitimate", "fraudulent", "borderline"}
PATTERNS = {"consistent_fabrication", "independent_record_contradiction", "suspicious_payee", "keyword_free",
            "prose_contradiction"}
CHECKS = ("BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION")
RESPONSES = {"CONFIRMED", "CONTRADICTED", "UNREACHABLE", "INCONCLUSIVE"}
PRIOR_CORPORA = ["fundraising_scenarios.jsonl", "independent_benchmark_100.jsonl", "independent_test_150.jsonl",
                 "development_scenarios_v1.jsonl", "development_scenarios_v2.jsonl",
                 "development_scenarios_v3.jsonl", "final_test_scenarios_v3.jsonl"]
DEFAULT_QUOTAS = {"legitimate": 30, "fraudulent": 30, "borderline": 15}
MIN_PATTERN_SHARE = 0.15


def tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").casefold()))


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _case_errors(case: dict) -> list:
    errors = []
    for key in ("case_id", "scenario_group", "author_id", "provenance", "category", "author_intended_label", "input",
                "external_environment"):
        if key not in case:
            errors.append(f"missing field '{key}'")
    if errors:
        return errors
    if case["category"] not in CATEGORIES:
        errors.append(f"category must be one of {sorted(CATEGORIES)}")
    if case["author_intended_label"] not in LABELS:
        errors.append(f"author_intended_label must be one of {sorted(LABELS)}")
    if case["provenance"] not in {"synthetic", "real_deidentified"} or \
            case.get("synthetic") is not (case["provenance"] == "synthetic"):
        errors.append("provenance must be synthetic|real_deidentified and `synthetic` must match it")
    if case["author_intended_label"] == "fraudulent" and case.get("pattern") not in PATTERNS:
        errors.append(f"fraud cases need a pattern from {sorted(PATTERNS)}")
    data = case["input"]
    for key in ("title", "story", "goal_amount", "documents"):
        if key not in data:
            errors.append(f"input.{key} missing")
    titles = [d.get("title") for d in data.get("documents", [])]
    if any(not d.get("content", "").strip() for d in data.get("documents", [])):
        errors.append("every document needs non-empty content")
    gold = case.get("gold_evidence_titles") or []
    if case["author_intended_label"] in ("fraudulent", "borderline") and not gold:
        errors.append("fraud and borderline cases need gold_evidence_titles")
    if any(title not in titles for title in gold):
        errors.append("gold_evidence_titles must name documents in this case")
    environment = case["external_environment"]
    for check in CHECKS:
        entry = environment.get(check)
        if not entry or entry.get("independent_response") not in RESPONSES:
            errors.append(f"external_environment.{check}.independent_response must be one of {sorted(RESPONSES)}")
        supplied = (entry or {}).get("campaign_supplied_contact")
        if supplied and (supplied.get("response") not in RESPONSES or not isinstance(supplied.get("printed_in_uploads"), bool)):
            errors.append(f"external_environment.{check}.campaign_supplied_contact needs printed_in_uploads and response")
    if case["author_intended_label"] == "fraudulent" and case.get("pattern") == "consistent_fabrication" and all(
            environment.get(c, {}).get("independent_response") == "CONFIRMED" for c in CHECKS):
        errors.append("a consistent_fabrication case must be revealed by at least one independent party")
    return errors


def validate(path: Path, quotas=None, check_prior=True) -> dict:
    quotas = DEFAULT_QUOTAS if quotas is None else quotas
    cases, errors, warnings = [], [], []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line {number}: not valid JSON")
            continue
        errors += [f"{case.get('case_id', f'line {number}')}: {e}" for e in _case_errors(case)]
        cases.append(case)
    ids = Counter(c.get("case_id") for c in cases)
    errors += [f"duplicate case_id {i}" for i, n in ids.items() if n > 1]
    groups = defaultdict(list)
    for case in cases:
        groups[case.get("scenario_group")].append(case)
    for group, members in groups.items():
        if len(members) > 3:
            errors.append(f"group {group} has {len(members)} cases (maximum 3)")
        stories = [tokens(m.get("input", {}).get("story")) for m in members]
        for i in range(len(stories)):
            for j in range(i + 1, len(stories)):
                if jaccard(stories[i], stories[j]) >= 0.9:
                    warnings.append(f"group {group}: cases {members[i]['case_id']} and {members[j]['case_id']} are near-copies")
    # quotas: groups per category and label
    group_label = {g: Counter(m.get("author_intended_label") for m in ms).most_common(1)[0][0] for g, ms in groups.items()}
    group_category = {g: ms[0].get("category") for g, ms in groups.items()}
    coverage = {cat: dict(Counter(group_label[g] for g in groups if group_category[g] == cat)) for cat in sorted(CATEGORIES)}
    for category in CATEGORIES:
        for label, minimum in quotas.items():
            have = coverage.get(category, {}).get(label, 0)
            if have < minimum:
                errors.append(f"{category}: {have} {label} groups (protocol minimum {minimum})")
        fraud_groups = [g for g in groups if group_category[g] == category and group_label[g] == "fraudulent"]
        patterns = Counter(groups[g][0].get("pattern") for g in fraud_groups)
        for pattern in PATTERNS:
            if fraud_groups and quotas.get("fraudulent", 0) and patterns[pattern] / len(fraud_groups) < MIN_PATTERN_SHARE:
                errors.append(f"{category}: pattern {pattern} is {patterns[pattern]}/{len(fraud_groups)} fraud groups "
                              f"(minimum {int(MIN_PATTERN_SHARE * 100)}%)")
    # keyword-free cases must avoid every known lexicon
    from check_keyword_free_fraud import keyword_hits, lexicons
    patterns_compiled = lexicons()
    for case in cases:
        if case.get("pattern") == "keyword_free":
            data = case.get("input", {})
            text = "\n".join([data.get("title", ""), data.get("story", "")] +
                             [d.get("content", "") for d in data.get("documents", [])])
            if keyword_hits(text, patterns_compiled):
                errors.append(f"{case['case_id']}: keyword_free case matches a known red-flag lexicon")
    # novelty against every previously used corpus
    if check_prior:
        prior = []
        for name in PRIOR_CORPORA:
            corpus = Path(__file__).with_name(name)
            if corpus.exists():
                prior += [tokens(json.loads(l).get("input", {}).get("story")) for l in corpus.read_text().splitlines() if l.strip()]
        for case in cases:
            story = tokens(case.get("input", {}).get("story"))
            if any(jaccard(story, p) >= 0.8 for p in prior):
                errors.append(f"{case['case_id']}: story is a near-duplicate of a previously used corpus")
    return {"file": str(path), "cases": len(cases), "groups": len(groups),
            "groups_by_category_and_label": coverage, "errors": errors, "warnings": warnings,
            "valid": not errors, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def kappa(sheet_a: Path, sheet_b: Path) -> dict:
    """Cohen's kappa on the `label` column for case_ids present in both sheets."""
    read = lambda p: {r["case_id"]: r["label"].strip() for r in csv.DictReader(p.open(encoding="utf-8"))}
    a, b = read(sheet_a), read(sheet_b)
    shared = sorted(set(a) & set(b))
    if not shared:
        return {"cases": 0, "kappa": None}
    observed = sum(a[i] == b[i] for i in shared) / len(shared)
    categories = set(a[i] for i in shared) | set(b[i] for i in shared)
    expected = sum((sum(a[i] == c for i in shared) / len(shared)) * (sum(b[i] == c for i in shared) / len(shared))
                   for c in categories)
    value = 1.0 if expected == 1 else (observed - expected) / (1 - expected)
    return {"cases": len(shared), "observed_agreement": round(observed, 4), "kappa": round(value, 4),
            "disagreements": [i for i in shared if a[i] != b[i]]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate")
    v.add_argument("submission", type=Path)
    v.add_argument("--no-quotas", action="store_true", help="structural checks only (for partial drafts)")
    v.add_argument("--seal", type=Path, help="write a sealed manifest here if the submission is valid")
    a = sub.add_parser("agreement")
    a.add_argument("sheet_a", type=Path)
    a.add_argument("sheet_b", type=Path)
    args = parser.parse_args(argv)
    if args.command == "agreement":
        result = kappa(args.sheet_a, args.sheet_b)
    else:
        result = validate(args.submission, quotas={} if args.no_quotas else None)
        if args.seal and result["valid"] and not args.no_quotas:
            args.seal.write_text(json.dumps({**result, "sealed_at_utc": datetime.now(timezone.utc).isoformat()},
                                            indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
