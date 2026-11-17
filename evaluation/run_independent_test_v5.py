"""Runner for the v5 independent evaluation of hybrid v3.  No API call unless every live precondition holds.

    plan [--submission S]                     offline estimate: requests, elapsed days, tokens, cost, designs
    integrity                                 freezes, production default model, clean app/ tree
    dry-run SUBMISSION --run-dir D [--script S] [--pilot] [--resume]
                                              ENG- fixtures or pilot cases only, scripted fake Gemini, no network
    status RUN_DIR                            counters only; never decisions or labels
    seal-kit / verify-kit                     seal (after the owner approves the pre-registration) / verify the kit
    execute SUBMISSION --seal SEAL --run-dir D --scope pilot|main --authorisation AUTH.json
            [--labels FINAL --label-seal SEAL] [--resume]
                                              LIVE.  Refuses unless the kit is sealed, every freeze verifies, the
                                              submission (and, for main, the labels) are sealed, the owner's written
                                              authorisation matches the plan, SEVAFUND_GEMINI_EVAL_APPROVED=1 and a key
                                              is configured.  The model is fixed by the pre-registration.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from independent_v5 import config, kit, runner  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--submission", type=Path)
    sub.add_parser("integrity")
    d = sub.add_parser("dry-run")
    d.add_argument("submission", type=Path)
    d.add_argument("--run-dir", type=Path, required=True)
    d.add_argument("--script", type=Path, default=config.FIXTURES / "gemini_script.json")
    d.add_argument("--pilot", action="store_true")
    d.add_argument("--resume", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("run_dir", type=Path)
    sub.add_parser("seal-kit")
    sub.add_parser("verify-kit")
    e = sub.add_parser("execute")
    e.add_argument("submission", type=Path)
    e.add_argument("--seal", type=Path, required=True)
    e.add_argument("--run-dir", type=Path, required=True)
    e.add_argument("--scope", choices=["pilot", "main"], required=True)
    e.add_argument("--authorisation", type=Path, required=True)
    e.add_argument("--labels", type=Path)
    e.add_argument("--label-seal", type=Path)
    e.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "plan":
        result = runner.plan(args.submission)
    elif args.command == "integrity":
        result = runner.integrity()
    elif args.command == "dry-run":
        script = json.loads(args.script.read_text(encoding="utf-8"))
        result = runner.dry_run(args.submission, args.run_dir, script, pilot=args.pilot, resume=args.resume)
    elif args.command == "status":
        result = runner.status(args.run_dir)
    elif args.command == "seal-kit":
        result = kit.seal()
    elif args.command == "verify-kit":
        result = kit.verify()
    else:
        result = runner.execute(args.submission, args.seal, args.run_dir, args.scope, args.authorisation,
                                args.labels, args.label_seal, args.resume)
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
