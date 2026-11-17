"""Score a finished v5 run against the sealed adjudicated labels (offline; never imports app/).

    score --run-dir RUN --labels FINAL.csv --label-seal SEAL.json --submission S.jsonl --out OUT_DIR
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from independent_v5 import scorer  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("score")
    s.add_argument("--run-dir", type=Path, required=True)
    s.add_argument("--labels", type=Path, required=True)
    s.add_argument("--label-seal", type=Path, required=True)
    s.add_argument("--submission", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = scorer.score(args.run_dir, args.labels, args.label_seal, args.submission, args.out)
    print(json.dumps({"out": str(args.out), "run_status": result["run_status"],
                      "all_gates_pass": result["criteria_hybrid_v3"]["all_gates_pass"]}, indent=2))
    return result


if __name__ == "__main__":
    main()
