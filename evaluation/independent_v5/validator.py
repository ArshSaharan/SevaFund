"""Coordinator-side validation of authored submissions, pilot sets and the participant registry (offline).

Never runs a verifier and never reads labels.  Reads production chunking (app.services.rag.chunk_document) and the
keyword lexicons read-only; everything else is standard library.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config, datecheck, exclusion
from .participants import eligible, load as load_participants

FORMS = {"structured", "prose"}
HIDDEN_FROM_LABELLERS = ["author_id", "author_intended_label", "author_intended_documentation", "mechanism", "form",
                         "keyword_free", "incomplete_subtype", "gold_evidence_titles", "date_facts", "date_sensitive",
                         "author_notes", "llm_assisted", "intended_detectable_from_dossier"]


# ------------------------------------------------------------------ per case
def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def case_errors(case: dict, prereg: dict, prefix: str) -> List[str]:
    design = prereg["design"]
    errors = []
    required = ["case_id", "scenario_group", "author_id", "provenance", "synthetic", "llm_assisted", "category",
                "author_intended_label", "author_intended_documentation", "input", "external_environment",
                "date_sensitive", "date_facts"]
    missing = [k for k in required if k not in case]
    if missing:
        return [f"missing fields {missing}"]
    cid, group = str(case["case_id"]), str(case["scenario_group"])
    if not cid.startswith(prefix):
        errors.append(f"case_id must start with '{prefix}'")
    if not re.fullmatch(re.escape(group) + r"-[A-C]", cid):
        errors.append("case_id must be <scenario_group>-A, -B or -C")
    for other in {design["case_id_prefix"], design["pilot_case_id_prefix"], design["engineering_case_id_prefix"]} - {prefix}:
        if cid.startswith(other) and not prefix.startswith(other):
            errors.append(f"case_id prefix '{other}' is not allowed here")
    if case["category"] not in design["categories"]:
        errors.append(f"category must be one of {design['categories']}")
    label, documentation = case["author_intended_label"], case["author_intended_documentation"]
    if label not in config.LABELS:
        errors.append(f"author_intended_label must be one of {list(config.LABELS)}")
    if documentation not in config.DOCUMENTATION:
        errors.append(f"author_intended_documentation must be one of {list(config.DOCUMENTATION)}")
    if case["provenance"] not in {"synthetic", "real_deidentified"} or case["synthetic"] is not (case["provenance"] == "synthetic"):
        errors.append("provenance must be synthetic or real_deidentified, and `synthetic` must match it")
    if not isinstance(case["llm_assisted"], bool):
        errors.append("llm_assisted must be true or false")
    if label == "fraudulent":
        if case.get("mechanism") not in design["mechanisms"]:
            errors.append(f"fraud cases need a mechanism from {design['mechanisms']}")
        if case.get("mechanism") == "document_contradiction" and case.get("form") not in FORMS:
            errors.append("document_contradiction needs form structured or prose")
        if not isinstance(case.get("keyword_free"), bool):
            errors.append("fraud cases need keyword_free true or false")
        if not isinstance(case.get("intended_detectable_from_dossier"), bool):
            errors.append("fraud cases need intended_detectable_from_dossier true or false")
    elif case.get("mechanism"):
        errors.append("only fraud cases have a mechanism")
    if label == "legitimate" and documentation == "incomplete" and case.get("incomplete_subtype") not in design["incomplete_subtypes"]:
        errors.append(f"legitimate incomplete cases need incomplete_subtype from {design['incomplete_subtypes']}")
    data = case["input"]
    for key in ("title", "category", "story", "goal_amount", "goal_currency", "beneficiary_name", "beneficiary_type",
                "city", "state", "submitted_on", "documents"):
        if key not in data:
            errors.append(f"input.{key} missing")
    if errors:
        return errors
    if data["category"] != case["category"]:
        errors.append("input.category must equal category")
    if not _number(data["goal_amount"]) or data["goal_amount"] <= 0:
        errors.append("input.goal_amount must be a positive number")
    if data["goal_currency"] != "INR":
        errors.append("input.goal_currency must be INR")
    documents = data["documents"]
    titles = [d.get("title") for d in documents] if isinstance(documents, list) else []
    if not titles:
        errors.append("input.documents must be a non-empty list")
    if len(set(titles)) != len(titles):
        errors.append("document titles must be unique within a case")
    if any(not (d.get("content") or "").strip() or not d.get("title") or not d.get("doc_type") for d in documents):
        errors.append("every document needs a title, a doc_type and non-empty content")
    gold = case.get("gold_evidence_titles") or []
    if (label != "legitimate" or documentation == "incomplete") and not gold:
        errors.append("fraud, borderline and incomplete cases need gold_evidence_titles")
    if any(t not in titles for t in gold):
        errors.append("gold_evidence_titles must name documents in this case")
    environment = case["external_environment"]
    for party in config.ENVIRONMENT_PARTIES:
        entry = environment.get(party) if isinstance(environment, dict) else None
        if not isinstance(entry, dict) or entry.get("independent_response") not in config.RESPONSES:
            errors.append(f"external_environment.{party}.independent_response must be one of {sorted(config.RESPONSES)}")
            continue
        supplied = entry.get("campaign_supplied_contact")
        if supplied is not None and (supplied.get("response") not in config.RESPONSES
                                     or not isinstance(supplied.get("printed_in_uploads"), bool)):
            errors.append(f"external_environment.{party}.campaign_supplied_contact needs printed_in_uploads and response")
    cost = environment.get("COST_ISSUER", {}) if isinstance(environment, dict) else {}
    for key in ("amount_stated_inr", "other_payers_inr"):
        if key not in cost or not (cost[key] is None or (_number(cost[key]) and cost[key] >= 0)):
            errors.append(f"external_environment.COST_ISSUER.{key} must be a non-negative number or null")
    if label == "fraudulent" and case.get("mechanism") == "consistent_fabrication" and all(
            environment.get(p, {}).get("independent_response") == "CONFIRMED" for p in config.ENVIRONMENT_PARTIES):
        errors.append("a consistent_fabrication case must be revealed by at least one independent party")
    return errors


def chunk_count(case: dict) -> int:
    from app.services.rag import chunk_document          # production chunking, read-only
    return sum(len(chunk_document(d.get("content", ""), {"title": d.get("title"), "doc_type": d.get("doc_type")}))
               for d in case["input"]["documents"])


def _keyword_patterns():
    if str(config.EVALUATION) not in sys.path:
        sys.path.insert(0, str(config.EVALUATION))
    from check_keyword_free_fraud import keyword_hits, lexicons
    return keyword_hits, lexicons()


# ------------------------------------------------------------------ submission
def _stratum(case: dict) -> str:
    return config.stratum(case.get("author_intended_label"), case.get("author_intended_documentation"))


def _quota_errors(cases: List[dict], groups: Dict[str, List[dict]], prereg: dict, profile: str) -> List[str]:
    design, errors = prereg["design"], []
    engineering = profile == "engineering"
    quotas = prereg["engineering_profile"]["groups_per_category"] if engineering else design["groups_per_category"]
    max_cases = prereg["engineering_profile"]["max_cases"] if engineering else design["max_cases"]
    if len(cases) > max_cases:
        errors.append(f"{len(cases)} cases exceeds the design maximum of {max_cases}")
    first = {g: members[0] for g, members in groups.items()}
    for category in design["categories"]:
        in_cat = [g for g, c in first.items() if c["category"] == category]
        have = Counter(_stratum(first[g]) for g in in_cat)
        for s, minimum in quotas.items():
            if have[s] < minimum:
                errors.append(f"{category}: {have[s]} {s} groups (minimum {minimum})")
        fraud_groups = [g for g in in_cat if _stratum(first[g]) == "F"]
        if not engineering and fraud_groups:
            mech = Counter(first[g].get("mechanism") for g in fraud_groups)
            for m in design["mechanisms"]:
                if mech[m] / len(fraud_groups) < design["mechanism_min_share_per_category"]:
                    errors.append(f"{category}: mechanism {m} is {mech[m]}/{len(fraud_groups)} fraud groups "
                                  f"(minimum {design['mechanism_min_share_per_category']:.0%})")
            detectable = sum(bool(first[g].get("intended_detectable_from_dossier")) for g in fraud_groups)
            if detectable / len(fraud_groups) < design["intended_detectable_min_share_per_category"]:
                errors.append(f"{category}: {detectable}/{len(fraud_groups)} fraud groups are intended to be detectable "
                              f"from the dossier (minimum {design['intended_detectable_min_share_per_category']:.0%})")
        incomplete = Counter(first[g].get("incomplete_subtype") for g in in_cat if _stratum(first[g]) == "I")
        if not engineering:
            minimums = design["incomplete_subtype_min_groups_per_category"]
            for sub in design["incomplete_subtypes"]:
                minimum = minimums[sub] if isinstance(minimums, dict) else minimums
                if incomplete[sub] < minimum:
                    errors.append(f"{category}: {incomplete[sub]} incomplete groups of subtype {sub} (minimum {minimum})")
            cat_cases = [c for c in cases if c["category"] == category]
            sensitive = sum(bool(c.get("date_sensitive")) for c in cat_cases)
            if cat_cases and sensitive / len(cat_cases) < design["date_sensitive_min_share_per_category"]:
                errors.append(f"{category}: {sensitive}/{len(cat_cases)} date-sensitive cases "
                              f"(minimum {design['date_sensitive_min_share_per_category']:.0%})")
    fraud_groups = [g for g, c in first.items() if _stratum(c) == "F"]
    mechanisms = Counter(first[g].get("mechanism") for g in fraud_groups)
    if engineering:
        for m in design["mechanisms"]:
            if mechanisms[m] < prereg["engineering_profile"]["mechanism_min_groups_overall"]:
                errors.append(f"engineering profile: no fraud group with mechanism {m}")
        subtypes = Counter(c.get("incomplete_subtype") for c in first.values() if _stratum(c) == "I")
        for sub in design["incomplete_subtypes"]:
            if subtypes[sub] < prereg["engineering_profile"]["incomplete_subtype_min_groups_overall"]:
                errors.append(f"engineering profile: no incomplete group of subtype {sub}")
        if not any(c.get("date_sensitive") for c in cases):
            errors.append("engineering profile: no date-sensitive case")
    else:
        forms = Counter(first[g].get("form") for g in fraud_groups if first[g].get("mechanism") == "document_contradiction")
        total = sum(forms.values())
        for form in sorted(FORMS):
            if total and forms[form] / total < design["document_contradiction_form_min_share"]:
                errors.append(f"document_contradiction form {form} is {forms[form]}/{total} "
                              f"(minimum {design['document_contradiction_form_min_share']:.0%})")
        fraud_cases = [c for c in cases if _stratum(c) == "F"]
        free = [c for c in fraud_cases if c.get("keyword_free")]
        if fraud_cases and len(free) / len(fraud_cases) < design["keyword_free_min_share_of_fraud_cases"]:
            errors.append(f"{len(free)}/{len(fraud_cases)} fraud cases are keyword_free "
                          f"(minimum {design['keyword_free_min_share_of_fraud_cases']:.0%})")
        for m in design["mechanisms"]:
            if mechanisms[m] and not any(c.get("keyword_free") and c.get("mechanism") == m for c in fraud_cases):
                errors.append(f"no keyword_free fraud group with mechanism {m}")
    legit_complete = [c for c in cases if _stratum(c) == "L"]
    long_cases = sum(chunk_count(c) >= prereg["design"]["long_dossier_min_chunks"] for c in legit_complete)
    needed = 1 if engineering else prereg["design"]["long_dossier_min_share_of_L_cases"] * len(legit_complete)
    if legit_complete and long_cases < needed:
        errors.append(f"{long_cases}/{len(legit_complete)} legitimate-complete cases have at least "
                      f"{prereg['design']['long_dossier_min_chunks']} chunks (needed {needed:g})")
    return errors


def validate_submission(path: Path, profile: str = "full", participants: Optional[Path] = None,
                        pilot: Optional[Path] = None, is_pilot: bool = False, prereg: Optional[dict] = None,
                        registry: Path = config.EXCLUSION_REGISTRY, check_quotas: bool = True) -> dict:
    prereg = prereg or config.load_prereg()
    design = prereg["design"]
    if profile not in {"full", "engineering"}:
        raise ValueError("profile must be full or engineering")
    if profile == "engineering":
        prefix = design["engineering_case_id_prefix"] + ("PIL-" if is_pilot else "")
    else:
        prefix = design["pilot_case_id_prefix"] if is_pilot else design["case_id_prefix"]
    errors, warnings, cases = [], [], []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line {number}: not valid JSON")
            continue
        if not isinstance(case, dict):
            errors.append(f"line {number}: not a JSON object")
            continue
        problems = case_errors(case, prereg, prefix)
        if not problems:
            date_errors, date_warnings = datecheck.check_case(case)
            problems += date_errors
            warnings += [f"{case['case_id']}: {w}" for w in date_warnings]
        errors += [f"{case.get('case_id', f'line {number}')}: {e}" for e in problems]
        cases.append(case)
    ids = Counter(c.get("case_id") for c in cases)
    errors += [f"duplicate case_id {i}" for i, n in ids.items() if n > 1]
    groups: Dict[str, List[dict]] = defaultdict(list)
    for case in cases:
        groups[case.get("scenario_group")].append(case)
    for group, members in groups.items():
        if len(members) > design["max_cases_per_group"]:
            errors.append(f"group {group} has {len(members)} cases (maximum {design['max_cases_per_group']})")
        for key in ("author_id", "category", "author_intended_label", "author_intended_documentation"):
            if len({str(m.get(key)) for m in members}) > 1:
                errors.append(f"group {group}: every case must share {key}")
    structurally_valid = not errors
    if structurally_valid and check_quotas and not is_pilot:
        errors += _quota_errors(cases, groups, prereg, profile)
    if is_pilot and profile == "full" and len(cases) != design["pilot_cases"]:
        errors.append(f"the pilot set needs exactly {design['pilot_cases']} cases")
    if structurally_valid:
        keyword_hits, patterns = _keyword_patterns()
        for case in cases:
            if case.get("keyword_free"):
                data = case["input"]
                text = "\n".join([data["title"], data["story"]] + [d["content"] for d in data["documents"]])
                if keyword_hits(text, patterns):
                    errors.append(f"{case['case_id']}: keyword_free case contains a known red-flag or lexicon term")
        errors += _duplicate_errors(cases, groups, prereg, registry, pilot, warnings)
    participant_info = None
    if participants is not None:
        participant_info = load_participants(participants)
        errors += participant_info["errors"]
        for author in sorted({c.get("author_id") for c in cases}):
            reasons = eligible(participant_info["participants"].get(str(author)), "author")
            errors += [f"author {author}: {r}" for r in reasons]
    elif profile == "full":
        errors.append("the participant registry is required for a full submission")
    strata = Counter(f"{members[0].get('category')}|{_stratum(members[0])}" for members in groups.values())
    return {"file": str(path), "profile": profile, "pilot": is_pilot, "cases": len(cases), "groups": len(groups),
            "groups_by_category_and_stratum": dict(sorted(strata.items())),
            "llm_assisted_cases": sum(bool(c.get("llm_assisted")) for c in cases),
            "non_synthetic_cases": sum(c.get("provenance") != "synthetic" for c in cases),
            "errors": errors, "warnings": warnings, "valid": not errors,
            "sha256": config.sha256_file(path)}


def _duplicate_errors(cases, groups, prereg, registry, pilot, warnings) -> List[str]:
    thresholds = prereg["duplicates"]
    errors = []
    prior_items, problems, registry_warnings, literal_hashes = exclusion.load_prior(registry)
    errors += [f"exclusion registry: {p}" for p in problems]
    warnings += [f"exclusion registry: {w}" for w in registry_warnings]
    own_ids = {c["case_id"] for c in cases}
    prior_items = [i for i in prior_items if i.get("case_id") not in own_ids or not str(i.get("case_id", "")).startswith("ENG-")]
    if pilot is not None:
        for case in config.read_jsonl(pilot):
            if case.get("case_id") in own_ids:
                errors.append(f"{case.get('case_id')}: a pilot case ID cannot appear in the test set")
            prior_items += [{"source": str(pilot), "case_id": case.get("case_id"), "field": f, "text": t}
                            for f, t in exclusion.case_texts(case)]
    prior = exclusion.DuplicateIndex(thresholds).add_all(prior_items)
    current = exclusion.DuplicateIndex(thresholds)
    min_words = thresholds["min_words_for_exact_match"]
    for group, members in groups.items():
        own = []
        for case in members:
            for field, text in exclusion.case_texts(case):
                for match in prior.query(text, field):
                    errors.append(f"{case['case_id']} {field}: {exclusion.describe(match)}")
                if len(exclusion.normalise(text).split()) >= min_words and exclusion.exact_hash(text) in literal_hashes:
                    errors.append(f"{case['case_id']} {field}: EXACT duplicate of a registered test-suite text")
                for match in current.query(text, field, skip=lambda item: item.get("group") == group):
                    errors.append(f"{case['case_id']} {field}: duplicates scenario group {match.other['group']} "
                                  f"({exclusion.describe(match)})")
                own.append({"source": "submission", "case_id": case["case_id"], "group": group, "field": field,
                            "text": text})
        stories = [(c["case_id"], exclusion.shingles(exclusion.normalise(c["input"]["story"]))) for c in members]
        for i in range(len(stories)):
            for j in range(i + 1, len(stories)):
                a, b = stories[i][1], stories[j][1]
                if a and b and len(a & b) / len(a | b) >= thresholds["within_group_story_jaccard"]:
                    errors.append(f"group {group}: {stories[i][0]} and {stories[j][0]} are near-copies")
        seen = Counter(exclusion.exact_hash(i["text"]) for i in own if i["field"].startswith("document:"))
        if any(n > 1 for n in seen.values()):
            warnings.append(f"group {group}: identical documents are reused across its cases")
        current.add_all(own)
    return errors


# ------------------------------------------------------------------ outputs
def seal(result: dict, path: Path, extra: Optional[dict] = None) -> dict:
    if not result["valid"]:
        raise SystemExit("Refusing to seal an invalid submission")
    if Path(path).exists():
        raise SystemExit(f"{path} exists; a seal is never overwritten")
    record = {**result, **(extra or {}), "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
              "prereg_sha256": config.sha256_file(config.PREREG_PATH),
              "exclusion_registry_sha256": config.sha256_file(config.EXCLUSION_REGISTRY)}
    Path(path).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def blind_copy(submission: Path, out: Path) -> int:
    """The labellers' copy: author intent, mechanism, gold titles and date facts removed."""
    if Path(out).exists():
        raise SystemExit(f"{out} exists")
    rows = []
    for case in config.read_jsonl(submission):
        rows.append({k: v for k, v in case.items() if k not in HIDDEN_FROM_LABELLERS})
    Path(out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return len(rows)
