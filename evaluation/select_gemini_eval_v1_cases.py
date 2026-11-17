"""Select the 10-group diagnostic sample for the controlled Gemini 3.6 Flash evaluation (v1).

DIAGNOSTIC TESTING ON PREVIOUSLY AVAILABLE SYNTHETIC DATA - NOT INDEPENDENT VALIDATION.
Every case comes from a corpus that was already used to develop or evaluate earlier versions.

Selection rules (fixed before any Gemini call):
  * 10 distinct scenario groups: 4 legitimate, 4 fraudulent, 2 borderline; medical 4, education 3, community 3.
  * The three groups used in the two earlier 3-case pilots are excluded.
  * Groups chosen for the challenge types requested (see REASONS); within a 300-case group, variant 4 is taken
    (the 10 variants differ only in names, amounts and places).
  * No legitimate group in the 300-case corpus has incomplete evidence, so one legitimate case with a preliminary
    record is taken from the 150-case corpus (variant 2 of its family is the incomplete-evidence variant).
Source corpora are read only; the selected rows are copied into evaluation/gemini_eval_v1/cases.jsonl.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_keyword_free_fraud import keyword_hits, lexicons

OUT = Path(__file__).with_name("gemini_eval_v1")
PILOT_GROUPS = {"trial_slot_authorization_pending", "credential_calendar_shortfall", "market_food_cooling_room"}
SELECTION = [
    # (case_id, source corpus, reason)
    ("V3T-064", "final_test_scenarios_v3.jsonl",
     "Fraud with internally consistent but fabricated paperwork (estimate and service note agree); no red-flag keywords; frozen V3 approves this group."),
    ("V3T-244", "final_test_scenarios_v3.jsonl",
     "Fraud contradicted by an independent record (supplier ledger shows the invoice already paid and the account closed); frozen V3 misses this group."),
    ("V3T-154", "final_test_scenarios_v3.jsonl",
     "Fraud via an inconsistent quantity/amount (request for 54 tablets vs 31 recorded in the asset register); no red-flag keywords."),
    ("V3T-044", "final_test_scenarios_v3.jsonl",
     "Fraud via a contradiction between the campaign and its documents (pharmacy ledger is for a different patient and file)."),
    ("V3T-084", "final_test_scenarios_v3.jsonl",
     "Borderline: preliminary estimate with family contribution and net balance unconfirmed; frozen V3 approves this group (unsafe-approval test)."),
    ("V3T-194", "final_test_scenarios_v3.jsonl",
     "Borderline: cropped account screenshot without issue date or registrar seal; no red-flag keywords; frozen V3 approves this group."),
    ("V3T-224", "final_test_scenarios_v3.jsonl",
     "Legitimate community project whose wording matches known fraud lexicons (false-positive stress test)."),
    ("V3T-104", "final_test_scenarios_v3.jsonl",
     "Legitimate education access costs with a matching invoice and registration record; no red-flag keywords."),
    ("V3T-024", "final_test_scenarios_v3.jsonl",
     "Legitimate medical rehabilitation with unusual travel and lodging costs justified by a separate quote."),
    ("E150-102", "independent_test_150.jsonl",
     "Legitimate community project with incomplete supporting evidence (preliminary record; final authorization stamp still being processed)."),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    patterns = lexicons()
    rows, manifest = [], []
    for case_id, corpus, reason in SELECTION:
        path = Path(__file__).with_name(corpus)
        case = next(json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
                    if l.strip() and json.loads(l)["case_id"] == case_id)
        group = case.get("scenario_family") or case.get("scenario_group")
        if group in PILOT_GROUPS:
            raise SystemExit(f"{case_id} belongs to a pilot group")
        text = "\n".join([case["input"]["title"], case["input"]["story"]] +
                         [d["content"] for d in case["input"].get("documents", [])])
        row = {"case_id": case_id, "ground_truth": case["ground_truth"], "scenario_family": group,
               "synthetic": True, "source_corpus": corpus, "input": case["input"]}
        rows.append(row)
        manifest.append({"case_id": case_id, "group": group, "category": case["input"]["category"],
                         "label": case["ground_truth"], "source_corpus": corpus, "source_sha256": sha(path),
                         "documents": len(case["input"].get("documents", [])),
                         "matches_known_red_flag_lexicon": bool(keyword_hits(text, patterns)),
                         "selection_reason": reason})
    groups = [m["group"] for m in manifest]
    assert len(set(groups)) == 10, "scenario groups must be distinct"
    labels = sorted(m["label"] for m in manifest)
    assert labels.count("legitimate") == 4 and labels.count("fraudulent") == 4 and labels.count("borderline") == 2
    return rows, manifest


def main():
    rows, manifest = build()
    OUT.mkdir(exist_ok=True)
    (OUT / "cases.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (OUT / "selection.json").write_text(json.dumps({
        "classification": "Diagnostic testing on previously available synthetic data; not independent validation.",
        "rules": __doc__.strip(), "cases": manifest,
        "cases_jsonl_sha256": sha(OUT / "cases.jsonl")}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
