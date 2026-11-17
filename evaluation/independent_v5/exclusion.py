"""Previously used scenarios can never enter the independent test (standard library only).

The registry (exclusion_registry.json) lists every earlier corpus by path and SHA-256: the 750 benchmark cases, the
development sets, the 10 historical Gemini cases, the date-aware templates and rendered cases, every long string
literal in the test suite, the v4 and v5 example cases and the v5 engineering fixtures.  Loading verifies each hash,
so a corpus cannot silently drop out.  Matching is on normalised text (digits -> '#'), so a copy with changed
amounts, dates or IDs is still caught; near-duplicates are found by 3-word-shingle Jaccard and containment.
"""
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from . import config

CASE_CORPORA = [
    "evaluation/final_test_scenarios_v3.jsonl", "evaluation/fundraising_scenarios.jsonl",
    "evaluation/independent_test_150.jsonl", "evaluation/independent_benchmark_100.jsonl",
    "evaluation/development_scenarios_v1.jsonl", "evaluation/development_scenarios_v2.jsonl",
    "evaluation/development_scenarios_v3.jsonl", "evaluation/development_scenarios_v3_contradiction_only.jsonl",
    "evaluation/development_scenarios_v3_initial.jsonl", "evaluation/gemini_eval_v1/cases.jsonl",
    "evaluation/runs/date_aware_dev_eval_live/rendered_cases.jsonl",
    "evaluation/independent_v5/engineering_fixtures/submission.jsonl",
    "evaluation/independent_v5/engineering_fixtures/pilot.jsonl",
    "evaluation/final_evaluation/scenarios.jsonl",            # the final developer-designed evaluation (2026-11-17)
]
SINGLE_CASES = ["evaluation/independent_test_v4/example_case.json", "evaluation/independent_test_v5/example_case.json"]
TEMPLATE_SETS = ["evaluation/date_aware_dev_eval/scenarios.json"]
LITERAL_MIN_CHARS = 60
_PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")


def normalise(text: str) -> str:
    text = _PLACEHOLDER.sub(" ", text or "").casefold()
    text = re.sub(r"\d", "#", text)
    text = re.sub(r"[^a-z#ऀ-෿]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def shingles(normalised: str, k: int = 3) -> set:
    words = normalised.split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def story_tokens(text: str) -> set:
    """v4's story check: raw token sets (kept for continuity)."""
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").casefold()))


def case_texts(case: dict) -> List[Tuple[str, str]]:
    data = case.get("input", {}) if isinstance(case.get("input"), dict) else {}
    texts = [("story", data.get("story") or "")]
    for document in data.get("documents") or []:
        texts.append((f"document:{document.get('title', '')}", document.get("content") or ""))
    return [(field, text) for field, text in texts if text and text.strip()]


# ------------------------------------------------------------------ registry
def _test_files() -> List[str]:
    return sorted(str(p.relative_to(config.ROOT)) for p in (config.ROOT / "tests").glob("test_*.py"))


def registered_sources() -> Dict[str, str]:
    sources = {p: "case_jsonl" for p in CASE_CORPORA}
    sources.update({p: "single_case_json" for p in SINGLE_CASES})
    sources.update({p: "template_json" for p in TEMPLATE_SETS})
    sources.update({p: "python_literals" for p in _test_files()})
    return sources


def _items(path: str, kind: str) -> List[dict]:
    full = config.ROOT / path
    items = []
    if kind == "case_jsonl":
        for case in config.read_jsonl(full):
            for field, text in case_texts(case):
                items.append({"source": path, "case_id": case.get("case_id"), "field": field, "text": text})
    elif kind == "single_case_json":
        case = json.loads(full.read_text(encoding="utf-8"))
        items += [{"source": path, "case_id": case.get("case_id"), "field": f, "text": t} for f, t in case_texts(case)]
    elif kind == "template_json":
        for case in json.loads(full.read_text(encoding="utf-8")).get("scenarios", []):
            items += [{"source": path, "case_id": case.get("case_id"), "field": f, "text": t} for f, t in case_texts(case)]
    elif kind == "python_literals":
        tree = ast.parse(full.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) >= LITERAL_MIN_CHARS:
                items.append({"source": path, "case_id": None, "field": f"literal@{node.lineno}", "text": node.value})
    return items


def exact_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode()).hexdigest()


def build_registry(path: Path = config.EXCLUSION_REGISTRY) -> dict:
    sources = {}
    for source, kind in sorted(registered_sources().items()):
        full = config.ROOT / source
        if not full.exists():
            raise SystemExit(f"Registered corpus is missing: {source}")
        items = _items(source, kind)
        entry = {"kind": kind, "sha256": config.sha256_file(full), "items": len(items)}
        if kind == "python_literals":          # test files evolve; keep their texts excluded even if later deleted
            entry["item_hashes"] = sorted({exact_hash(i["text"]) for i in items})
        sources[source] = entry
    registry = {"built_at_utc": datetime.now(timezone.utc).isoformat(), "sources": sources,
                "total_items": sum(s["items"] for s in sources.values()),
                "note": "Every listed text is excluded from the independent test. Dataset corpora must keep their "
                        "hashes; test files may change (their registered texts stay excluded by hash)."}
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return registry


def load_prior(path: Path = config.EXCLUSION_REGISTRY) -> Tuple[List[dict], List[str], List[str], set]:
    """All excluded texts (registered corpora plus every current test file), problems (a dataset corpus missing,
    changed or unregistered), warnings (a test file changed since registration) and the registered literal hashes."""
    registry = json.loads(path.read_text(encoding="utf-8"))
    problems, warnings, items, literal_hashes = [], [], [], set()
    current = registered_sources()
    for source, entry in registry["sources"].items():
        full = config.ROOT / source
        literal = entry["kind"] == "python_literals"
        literal_hashes.update(entry.get("item_hashes", []))
        if not full.exists():
            (warnings if literal else problems).append(f"registered corpus missing: {source}")
            continue
        if config.sha256_file(full) != entry["sha256"]:
            (warnings if literal else problems).append(f"registered corpus changed since the registry was built: {source}")
        items += _items(source, entry["kind"])
    for source in sorted(set(current) - set(registry["sources"])):
        if current[source] == "python_literals":
            items += _items(source, "python_literals")
            warnings.append(f"test file added after the registry was built (its literals are excluded too): {source}")
        else:
            problems.append(f"corpus not in the exclusion registry: {source}")
    return items, problems, warnings, literal_hashes


# ------------------------------------------------------------------ matching
@dataclass
class Match:
    kind: str            # EXACT | NEAR | STORY_TOKENS
    other: dict
    jaccard: float
    containment: float


class DuplicateIndex:
    def __init__(self, thresholds: dict):
        self.t = thresholds
        self.items: List[dict] = []
        self.exact: Dict[str, List[int]] = defaultdict(list)
        self.postings: Dict[str, List[int]] = defaultdict(list)
        self.shingle_sets: List[set] = []
        self.tokens: List[Optional[set]] = []

    def add(self, item: dict) -> None:
        index = len(self.items)
        norm = normalise(item["text"])
        self.items.append(item)
        if len(norm.split()) >= self.t["min_words_for_exact_match"]:
            self.exact[hashlib.sha256(norm.encode()).hexdigest()].append(index)
        sh = shingles(norm, self.t["shingle_words"])
        self.shingle_sets.append(sh)
        for s in sh:
            self.postings[s].append(index)
        self.tokens.append(story_tokens(item["text"]) if item.get("field") == "story" else None)

    def add_all(self, items: Iterable[dict]) -> "DuplicateIndex":
        for item in items:
            self.add(item)
        return self

    def query(self, text: str, field: str = "", skip=None, max_postings: int = 400) -> List[Match]:
        skip = skip or (lambda item: False)
        norm = normalise(text)
        matches: Dict[int, Match] = {}
        if len(norm.split()) >= self.t["min_words_for_exact_match"]:
            for index in self.exact.get(hashlib.sha256(norm.encode()).hexdigest(), []):
                if not skip(self.items[index]):
                    matches[index] = Match("EXACT", self.items[index], 1.0, 1.0)
        sh = shingles(norm, self.t["shingle_words"])
        long_min, short_min = self.t["min_shingles_for_near_match"], self.t["min_shingles_for_short_match"]
        if len(sh) >= short_min:
            counts = Counter()
            for s in sh:
                posting = self.postings.get(s, [])
                if len(posting) <= max_postings:
                    counts.update(posting)
            for index, shared in counts.items():
                if index in matches or skip(self.items[index]):
                    continue
                other = self.shingle_sets[index]
                if len(other) < short_min:
                    continue
                inter = len(sh & other)
                jaccard = inter / len(sh | other)
                containment = max(inter / len(sh), inter / len(other))
                if len(sh) >= long_min and len(other) >= long_min:
                    near = jaccard >= self.t["near_duplicate_jaccard"] or containment >= self.t["near_duplicate_containment"]
                else:                      # a short text reused almost verbatim inside another text
                    near = inter / min(len(sh), len(other)) >= self.t["short_text_containment"]
                if near:
                    matches[index] = Match("NEAR", self.items[index], round(jaccard, 3), round(containment, 3))
        if field == "story":
            mine = story_tokens(text)
            for index, theirs in enumerate(self.tokens):
                if theirs and index not in matches and not skip(self.items[index]) and mine and \
                        len(mine & theirs) / len(mine | theirs) >= self.t["story_token_jaccard_v4"]:
                    matches[index] = Match("STORY_TOKENS", self.items[index], 1.0, 1.0)
        return list(matches.values())


def describe(match: Match) -> str:
    other = match.other
    where = other.get("case_id") or other.get("source")
    return (f"{match.kind} duplicate of {other.get('source')} [{where}] {other.get('field')} "
            f"(jaccard {match.jaccard}, containment {match.containment})")
