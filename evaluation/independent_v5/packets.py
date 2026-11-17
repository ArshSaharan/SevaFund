"""Role packets: the only material a participant receives (standard library only; no app import).

Participants never get repository access, source code, prompts, rule or keyword lists, earlier datasets, or any
system output.  The coordinator builds one packet per role from an allowlist, outside the repository, and sends it.
Labellers and the adjudicator also receive the blinded cases (from `prepare_independent_data_v5.py blind`), and the
adjudicator receives the disagreement sheet.  The packet manifest records each file's SHA-256, so the coordinator can
show exactly what each participant was given.
"""
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import config
from .labels import ADJUDICATION_FIELDS
from .validator import HIDDEN_FROM_LABELLERS

COMMON = ["INDEPENDENCE_DECLARATION.md", "REQUIRED_EVIDENCE_POLICY.md"]
PACKETS = {
    "author": COMMON + ["AUTHORING_GUIDE.md", "example_case.json"],
    "labeller": COMMON + ["LABELLING_GUIDE.md", "labeling_sheet_template.csv"],
    "adjudicator": COMMON + ["LABELLING_GUIDE.md", "adjudication_template.csv"],
}
LABELLED_PREFIXES = ("T5-", "ENG-")       # the pilot (P5-) is never labelled
NEVER_IN_A_PACKET = (".py", ".pyc", ".ipynb", ".sh", ".env", ".sqlite", ".db")

_NOT_GIVEN = ("You will not receive, and must not look for: the platform's source code, its rules, keyword lists or "
              "thresholds, the AI model or prompt it uses, any earlier test or benchmark data, or how any system "
              "decided any case. You need no account on any code repository.")

README = {
    "author": [
        "# SevaFund independent test: author packet", "",
        "You are writing realistic crowdfunding campaigns for an independent evaluation. Everything you need is in this "
        "folder.", "",
        "1. Read and sign `INDEPENDENCE_DECLARATION.md` and return it to the coordinator. Do not start writing until "
        "the coordinator confirms it is accepted.",
        "2. Read `AUTHORING_GUIDE.md`, `REQUIRED_EVIDENCE_POLICY.md` and `example_case.json`.",
        "3. Use only the pseudonymous author ID and the block of group numbers the coordinator gives you.",
        "4. Write your cases in any plain-text editor, one JSON object per line, in a `.jsonl` file.",
        "5. Send the file to the coordinator only. The coordinator runs an automatic check and returns a list of "
        "problems by case ID. You fix them yourself; the coordinator never edits your cases.", "",
        _NOT_GIVEN, "",
        "Do not discuss your cases with labellers, other authors' cases, or the developers.",
    ],
    "labeller": [
        "# SevaFund independent test: labeller packet", "",
        "1. Read and sign `INDEPENDENCE_DECLARATION.md` and return it to the coordinator.",
        "2. Read `LABELLING_GUIDE.md` and `REQUIRED_EVIDENCE_POLICY.md`.",
        "3. `cases.jsonl` (if included) holds the blinded cases: the authors' intentions have been removed.",
        "4. Label every case on your own in a copy of `labeling_sheet_template.csv`. Remove the example row. Use your "
        "pseudonymous labeller ID.",
        "5. Return the sheet to the coordinator only. Do not compare answers with the other labeller.", "",
        _NOT_GIVEN,
    ],
    "adjudicator": [
        "# SevaFund independent test: adjudicator packet", "",
        "1. Read and sign `INDEPENDENCE_DECLARATION.md` and return it to the coordinator.",
        "2. Read `LABELLING_GUIDE.md` and `REQUIRED_EVIDENCE_POLICY.md`.",
        "3. `disagreements.csv` (if included) lists only the fields on which the two labellers disagreed, with both "
        "values. Read the case in `cases.jsonl`, then fill in `adjudicated_value`, your `adjudicator_id` and a "
        "`reason` for each row. Write `-` to record that the correct value is empty.",
        "4. Leave a row blank only if you genuinely cannot decide. An unresolved disagreement about truth or "
        "documentation makes that case borderline.",
        "5. Return the sheet to the coordinator only.", "",
        _NOT_GIVEN,
    ],
}


def _blinded_problems(path: Path) -> List[str]:
    problems = []
    for number, row in enumerate(config.read_jsonl(path), 1):
        leaked = sorted(set(row) & set(HIDDEN_FROM_LABELLERS))
        if leaked:
            problems.append(f"cases line {number}: fields hidden from labellers are present {leaked}")
        if not str(row.get("case_id", "")).startswith(LABELLED_PREFIXES):
            problems.append(f"cases line {number}: case_id must start with one of {LABELLED_PREFIXES}")
    return problems


def _sheet_problems(path: Path) -> List[str]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle), [])
    return [] if header == ADJUDICATION_FIELDS else [f"disagreement sheet header must be {ADJUDICATION_FIELDS}"]


def build(role: str, out: Path, cases: Optional[Path] = None, sheet: Optional[Path] = None) -> dict:
    if role not in PACKETS:
        raise SystemExit(f"role must be one of {sorted(PACKETS)}")
    out = Path(out).resolve()
    root = config.ROOT.resolve()
    if out == root or root in out.parents:
        raise SystemExit("Refusing to build a packet inside the repository: packets leave the developers' workspace")
    if out.exists():
        raise SystemExit(f"{out} exists; packets are never overwritten")
    if role == "author" and (cases or sheet):
        raise SystemExit("authors receive no cases and no label sheets")
    if sheet and role != "adjudicator":
        raise SystemExit("only the adjudicator receives the disagreement sheet")
    problems = (_blinded_problems(cases) if cases else []) + (_sheet_problems(sheet) if sheet else [])
    if problems:
        raise SystemExit("Refusing to build the packet: " + "; ".join(problems))

    out.mkdir(parents=True)
    for name in PACKETS[role]:
        shutil.copyfile(config.KIT / name, out / name)
    if cases:
        shutil.copyfile(cases, out / "cases.jsonl")
    if sheet:
        shutil.copyfile(sheet, out / "disagreements.csv")
    (out / "README.md").write_text("\n".join(README[role]) + "\n", encoding="utf-8")

    files = sorted(p.name for p in out.iterdir())
    expected = sorted(PACKETS[role] + ["README.md"] + (["cases.jsonl"] if cases else [])
                      + (["disagreements.csv"] if sheet else []))
    if files != expected or any(name.endswith(NEVER_IN_A_PACKET) for name in files):
        shutil.rmtree(out)
        raise SystemExit(f"packet contents {files} differ from the allowlist {expected}")
    manifest = {"role": role, "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "prereg_version": config.load_prereg()["version"],
                "files": {name: config.sha256_file(out / name) for name in files},
                "not_included": "source code, prompts, rule and keyword lists, earlier datasets, system outputs, "
                                "author intent (labellers and adjudicator)"}
    (out / "packet_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"role": role, "out": str(out), "files": files}
