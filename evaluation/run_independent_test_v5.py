"""Runner for the v5 independent evaluation of hybrid v3.  No API call unless every live precondition holds.

    plan [--submission S]                     offline estimate: requests, elapsed days, tokens, cost, designs
    integrity                                 freezes, production default model, clean app/ tree
    dry-run SUBMISSION --run-dir D [--script S] [--pilot] [--resume]
                                              ENG- fixtures or pilot cases only, scripted fake Gemini, no network
    status RUN_DIR                            counters only; never decisions or labels
    preseal-check [--registry R] [--out REPORT] [--no-rerun] [--no-tests]
                                              final offline checks before sealing (no network): criteria match the
                                              owner's approval, statistics meet the acceptance bounds and reproduce,
                                              tooling tests, freezes, exclusion registry, packets; lists what still blocks
    seal-kit --preseal-report REPORT          seal (status APPROVED and a passing report for the current kit required)
    verify-kit                                verify the sealed kit
    validate-statistics [--quick]             Monte Carlo check of the interval, test and power methods (offline);
                                              writes independent_test_v5/statistical_validation.json
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
    pc = sub.add_parser("preseal-check")
    pc.add_argument("--registry", type=Path)
    pc.add_argument("--out", type=Path)
    pc.add_argument("--no-rerun", action="store_true")
    pc.add_argument("--no-tests", action="store_true")
    sk = sub.add_parser("seal-kit")
    sk.add_argument("--preseal-report", type=Path)
    sub.add_parser("verify-kit")
    v = sub.add_parser("validate-statistics")
    v.add_argument("--quick", action="store_true")
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
    elif args.command == "preseal-check":
        from independent_v5 import preseal
        report = preseal.check(args.registry, rerun=not args.no_rerun, run_tests=not args.no_tests)
        if args.out:
            preseal.write_report(report, args.out)
        result = {k: v for k, v in report.items() if k not in ("kit_hashes",)}
    elif args.command == "seal-kit":
        result = kit.seal(args.preseal_report)
    elif args.command == "verify-kit":
        result = kit.verify()
    elif args.command == "validate-statistics":
        from independent_v5 import ci_validation
        full = ci_validation.run_all(quick=args.quick)
        full["coverage_summary"] = ci_validation.summarise_coverage(full["proportion_coverage"])
        if not args.quick:
            (config.KIT / "statistical_validation.json").write_text(json.dumps(full, indent=1) + "\n", encoding="utf-8")
        result = {k: full[k] for k in ("coverage_summary", "bootstrap_coverage", "paired_type1",
                                       "paired_difference_coverage", "comparison_power", "verdict_operating_characteristics", "zero_event_bounds")}
    else:
        result = runner.execute(args.submission, args.seal, args.run_dir, args.scope, args.authorisation,
                                args.labels, args.label_seal, args.resume)
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
