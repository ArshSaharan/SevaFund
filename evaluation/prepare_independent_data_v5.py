"""Coordinator tools for the v5 independent test data (offline; never runs a verifier, never calls an API).

    make-engineering-fixtures            regenerate the ENG- fixtures (engineering only, never test data)
    build-exclusion-registry             register every previously used corpus (before the kit is sealed)
    participants REGISTRY                independence check of the pseudonymous participant registry
    validate SUBMISSION [--profile full|engineering] [--participants P] [--pilot PILOT] [--seal OUT]
    validate-pilot PILOT [--profile ...] [--participants P] [--seal OUT]
    blind SUBMISSION OUT                 labellers' copy without author intent, mechanisms or gold titles
    labels-check SHEET --submission S [--participants P]
    labels-agreement SHEET_A SHEET_B
    labels-adjudication-template SHEET_A SHEET_B OUT
    labels-merge SHEET_A SHEET_B OUT [--adjudication ADJ] [--participants P]
    labels-seal FINAL OUT --sheet-a A --sheet-b B
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from independent_v5 import config, exclusion, labels, participants, validator  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("make-engineering-fixtures")
    sub.add_parser("build-exclusion-registry")
    p = sub.add_parser("participants")
    p.add_argument("registry", type=Path)
    for name in ("validate", "validate-pilot"):
        v = sub.add_parser(name)
        v.add_argument("submission", type=Path)
        v.add_argument("--profile", choices=["full", "engineering"], default="full")
        v.add_argument("--participants", type=Path)
        v.add_argument("--pilot", type=Path)
        v.add_argument("--seal", type=Path)
    b = sub.add_parser("blind")
    b.add_argument("submission", type=Path)
    b.add_argument("out", type=Path)
    c = sub.add_parser("labels-check")
    c.add_argument("sheet", type=Path)
    c.add_argument("--submission", type=Path, required=True)
    c.add_argument("--participants", type=Path)
    for name in ("labels-agreement", "labels-adjudication-template", "labels-merge"):
        x = sub.add_parser(name)
        x.add_argument("sheet_a", type=Path)
        x.add_argument("sheet_b", type=Path)
        if name != "labels-agreement":
            x.add_argument("out", type=Path)
        if name == "labels-merge":
            x.add_argument("--adjudication", type=Path)
            x.add_argument("--participants", type=Path)
    s = sub.add_parser("labels-seal")
    s.add_argument("final", type=Path)
    s.add_argument("out", type=Path)
    s.add_argument("--sheet-a", type=Path, required=True)
    s.add_argument("--sheet-b", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "make-engineering-fixtures":
        from independent_v5 import make_engineering_fixtures
        result = make_engineering_fixtures.build()
    elif args.command == "build-exclusion-registry":
        registry = exclusion.build_registry()
        result = {"sources": len(registry["sources"]), "total_items": registry["total_items"]}
    elif args.command == "participants":
        loaded = participants.load(args.registry)
        result = {"errors": loaded["errors"], "by_role": participants.summary(loaded)}
    elif args.command in ("validate", "validate-pilot"):
        result = validator.validate_submission(args.submission, args.profile, args.participants, args.pilot,
                                               is_pilot=args.command == "validate-pilot")
        if args.seal:
            extra = {"participants_sha256": config.sha256_file(args.participants) if args.participants else None,
                     "pilot_sha256": config.sha256_file(args.pilot) if args.pilot else None}
            validator.seal(result, args.seal, extra)
            result["sealed_to"] = str(args.seal)
    elif args.command == "blind":
        result = {"cases": validator.blind_copy(args.submission, args.out)}
    elif args.command == "labels-check":
        ids = [c["case_id"] for c in config.read_jsonl(args.submission)]
        authors = {c.get("author_id") for c in config.read_jsonl(args.submission)}
        registry = participants.load(args.participants)["participants"] if args.participants else None
        result = labels.check_sheet(args.sheet, ids, registry, authors)
    elif args.command == "labels-agreement":
        result = labels.agreement(args.sheet_a, args.sheet_b)
    elif args.command == "labels-adjudication-template":
        result = {"disagreements": labels.adjudication_template(args.sheet_a, args.sheet_b, args.out)}
    elif args.command == "labels-merge":
        registry = participants.load(args.participants)["participants"] if args.participants else None
        result = labels.merge(args.sheet_a, args.sheet_b, args.adjudication, args.out, registry)
    else:
        result = labels.seal(args.final, args.out, labels.agreement(args.sheet_a, args.sheet_b))
    print(json.dumps(result, indent=2, default=str))
    if isinstance(result, dict) and result.get("valid") is False:
        sys.exit(1)
    return result


if __name__ == "__main__":
    main()
