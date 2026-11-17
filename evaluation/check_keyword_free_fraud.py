"""Check that 'fraud without obvious red-flag keywords' cases really avoid every known lexicon.

Used by evaluation/independent_test_protocol_v4.md: a case tagged
`pattern: keyword_free` must match none of the production RED_FLAG_PATTERNS and
none of the V2/V3 semantic-signal regexes.  The authors must not see these
lists; this script is run by the protocol coordinator.

    python evaluation/check_keyword_free_fraud.py path/to/test_set.jsonl [--field pattern --value keyword_free]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.fraud_detector import RED_FLAG_PATTERNS
from app.services.development_verifier_v2 import semantic as v2_semantic
from app.services.development_verifier_v3 import semantic as v3_semantic


def lexicons():
    patterns = [("production:" + description[:40], re.compile(pattern, re.I)) for pattern, description, _ in RED_FLAG_PATTERNS]
    for name, module in (("v2", v2_semantic), ("v3", v3_semantic)):
        for attribute in dir(module):
            value = getattr(module, attribute)
            if isinstance(value, re.Pattern) and attribute.isupper() or (attribute.startswith("_") and
                                                                          isinstance(value, re.Pattern)):
                patterns.append((f"{name}:{attribute}", value))
    return patterns


def keyword_hits(text: str, patterns=None):
    return sorted({name for name, pattern in (patterns or lexicons()) if pattern.search(text or "")})


def check(path: Path, field: str, value: str):
    patterns = lexicons()
    failures = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        if case.get(field) != value:
            continue
        data = case["input"]
        text = "\n".join([data.get("title", ""), data.get("story", "")] +
                         [d.get("content", "") for d in data.get("documents", [])])
        hits = keyword_hits(text, patterns)
        if hits:
            failures.append({"case_id": case["case_id"], "matched": hits})
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--field", default="pattern")
    parser.add_argument("--value", default="keyword_free")
    args = parser.parse_args()
    problems = check(args.dataset, args.field, args.value)
    print(json.dumps({"cases_matching_a_known_lexicon": len(problems), "details": problems}, indent=2))
    sys.exit(1 if problems else 0)
