"""Read-only comparison of two Gemini pilot experiments run with the frozen framework.

Reads cache.jsonl / failures.jsonl / state.json / plan.json of each experiment and reports, per model:
successes vs timeouts, latency, API calls consumed, retrieval quality (and whether both runs retrieved the
same evidence), verification decisions, and disagreements between Gemini and the deterministic fallback.
It makes no API call and executes no verifier except the offline lexical retriever (for a retrieval
cross-check).  With a 3-case pilot these are integration/reliability observations, not accuracy estimates.
"""
import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_evaluation_framework as fw

RUNS = Path(__file__).with_name("runs")
API = ("gemini_no_rag", "gemini_rag")
FALLBACK_PAIR = {"gemini_no_rag": "heuristics_only", "gemini_rag": "heuristics_lexical"}


def load(experiment: str) -> dict:
    directory = RUNS / experiment
    cache = [json.loads(l) for l in (directory / "cache.jsonl").read_text().splitlines() if l.strip()]
    failures = [json.loads(l) for l in (directory / "failures.jsonl").read_text().splitlines() if l.strip()] \
        if (directory / "failures.jsonl").exists() else []
    plan = json.loads((directory / "plan.json").read_text())
    state = json.loads((directory / "state.json").read_text())
    results = {(r["config"], r["case_id"]): r for r in cache if r["stage"] == "result"}
    retrieval = {r["case_id"]: r for r in cache if r["stage"] == "retrieval"}
    return {"experiment": experiment, "plan": plan, "state": state, "results": results, "retrieval": retrieval,
            "failures": failures}


def nearest_rank(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else None


def generation_stats(run: dict) -> dict:
    out = {}
    for config in API:
        successes = [r for (c, _), r in run["results"].items() if c == config]
        failures = [f for f in run["failures"] if f["config"] == config and f["stage"] == "generation"]
        latencies = [r["generation_latency_ms"] / 1000 for r in successes]
        out[config] = {
            "attempted": len(successes) + len(failures), "succeeded": len(successes),
            "timeouts": sum(f["category"].endswith("TIMEOUT") for f in failures),
            "other_failures": dict(Counter(f["category"] for f in failures if not f["category"].endswith("TIMEOUT"))),
            "success_latency_seconds": {"n": len(latencies),
                                        "mean": round(statistics.mean(latencies), 2) if latencies else None,
                                        "p95_nearest_rank": round(nearest_rank(latencies, .95), 2) if latencies else None,
                                        "values": [round(v, 2) for v in sorted(latencies)]},
            "seconds_spent_on_failed_requests": round(sum(f.get("duration_seconds") or 0 for f in failures), 1),
        }
    embedding_failures = [f for f in run["failures"] if f["stage"] == "embedding"]
    out["embedding"] = {"attempted": len(run["retrieval"]) + len(embedding_failures),
                        "succeeded": len(run["retrieval"]),
                        "latency_seconds": [round(r["latency_ms"] / 1000, 2) for r in run["retrieval"].values()]}
    return out


def retrieval_comparison(a: dict, b: dict, cases: dict) -> dict:
    out = {}
    for case_id, case in cases.items():
        ra, rb = a["retrieval"].get(case_id), b["retrieval"].get(case_id)
        lexical = [c["title"] for c in fw.lexical_retrieve(case)]
        row = {"documents": len(case["input"].get("documents", [])), "lexical_titles": lexical}
        for name, record in (("run_a", ra), ("run_b", rb)):
            row[name] = None if not record else {
                "titles": [c["title"] for c in record["chunks"]], "relevance": [c["relevance"] for c in record["chunks"]],
                "document_coverage": record["retrieval"]["document_coverage"]}
        if ra and rb:
            row["identical_ranking_across_runs"] = row["run_a"]["titles"] == row["run_b"]["titles"]
            row["max_relevance_difference"] = round(max((abs(x - y) for x, y in zip(row["run_a"]["relevance"],
                                                                                   row["run_b"]["relevance"])), default=0), 6)
            row["embedding_vs_lexical_same_set"] = set(row["run_b"]["titles"]) == set(lexical)
        out[case_id] = row
    return out


def decisions(runs: dict, cases: dict) -> dict:
    table = {}
    for case_id, case in cases.items():
        row = {"label": case["ground_truth"], "category": case["input"]["category"]}
        first = next(iter(runs.values()))
        for config in ("heuristics_only", "heuristics_lexical"):
            record = first["results"].get((config, case_id))
            row[config] = None if not record else record["decision"]
        for model, run in runs.items():
            for config in ("gemini_no_rag", "gemini_rag", "hybrid"):
                record = run["results"].get((config, case_id))
                row[f"{config}@{model}"] = None if not record else record["decision"]
                if config == "hybrid" and record:
                    row["v3_decision"] = record["v3_decision"]
        table[case_id] = row
    return table


def disagreements(runs: dict, cases: dict) -> list:
    found = []
    for model, run in runs.items():
        for config, fallback in FALLBACK_PAIR.items():
            for case_id in cases:
                gemini, offline = run["results"].get((config, case_id)), run["results"].get((fallback, case_id))
                if not gemini or not offline:
                    continue
                if gemini["decision"] != offline["decision"] or gemini["flagged"] != offline["flagged"]:
                    found.append({"model": model, "case_id": case_id, "label": cases[case_id]["ground_truth"],
                                  "gemini_config": config, "gemini_decision": gemini["decision"],
                                  "gemini_flagged": gemini["flagged"], "gemini_red_flags": gemini.get("red_flags"),
                                  "fallback_config": fallback, "fallback_decision": offline["decision"],
                                  "fallback_flagged": offline["flagged"]})
    return found


def offline_reproducible(a: dict, b: dict) -> bool:
    keys = [k for k in a["results"] if k[0] in ("heuristics_only", "heuristics_lexical")]
    return bool(keys) and all(a["results"][k]["decision"] == b["results"].get(k, {}).get("decision")
                              and a["results"][k]["flagged"] == b["results"].get(k, {}).get("flagged") for k in keys)


def render(report) -> str:
    models = list(report["models"])
    lines = ["# Gemini model comparison on the frozen pilot", "",
             f"Same 3 synthetic cases ({', '.join(report['case_ids'])}), same frozen code (git `{report['freeze']['git_head'][:7]}`, "
             f"{report['freeze']['files_hashed']} files hash-identical before and after: **{report['freeze']['identical']}**), "
             "same production prompt, budget 9 requests per model, 6 s pacing, one HTTP request per counted call. "
             "Only the generation model differs. A 3-case pilot measures integration and reliability, **not accuracy**.", "",
             "## Reliability, latency and API usage", "",
             "| | " + " | ".join(models) + " |", "|---|" + "---:|" * len(models)]
    def cell(model, f):
        return f(report["models"][model])
    rows = [
        ("Requests consumed (generation / embedding)", lambda m: f"{m['calls']['generation']} / {m['calls']['embedding']}"),
        ("Gemini without RAG: succeeded / attempted", lambda m: f"{m['generation']['gemini_no_rag']['succeeded']} / {m['generation']['gemini_no_rag']['attempted']}"),
        ("Gemini with RAG: succeeded / attempted", lambda m: f"{m['generation']['gemini_rag']['succeeded']} / {m['generation']['gemini_rag']['attempted']}"),
        ("Timeouts (180 s)", lambda m: str(sum(m['generation'][c]['timeouts'] for c in API))),
        ("Other failures", lambda m: json.dumps({k: v for c in API for k, v in m['generation'][c]['other_failures'].items()}) or "—"),
        ("Success latency, mean (s)", lambda m: str(m["all_success_latency"]["mean"])),
        ("Success latency, p95 nearest-rank (s)", lambda m: str(m["all_success_latency"]["p95_nearest_rank"])),
        ("Successful latencies (s)", lambda m: ", ".join(str(v) for v in m["all_success_latency"]["values"]) or "—"),
        ("Seconds spent on failed requests", lambda m: str(sum(m['generation'][c]['seconds_spent_on_failed_requests'] for c in API))),
        ("Embedding requests succeeded", lambda m: f"{m['generation']['embedding']['succeeded']} / {m['generation']['embedding']['attempted']}"),
    ]
    for title, f in rows:
        lines.append(f"| {title} | " + " | ".join(cell(m, f) for m in models) + " |")
    lines += ["", "With n ≤ 6 successes, the nearest-rank p95 equals the slowest observed response.", "",
              "## Evidence retrieval", "", "| Case | Docs | Embedding ranking (run A) | Same in run B | Max relevance Δ | Coverage | Lexical retrieves same docs |",
              "|---|---:|---|---|---:|---:|---|"]
    for case_id, r in report["retrieval"].items():
        a = r["run_a"] or {}
        lines.append(f"| {case_id} | {r['documents']} | {', '.join(a.get('titles', [])) or '—'} | "
                     f"{r.get('identical_ranking_across_runs', '—')} | {r.get('max_relevance_difference', '—')} | "
                     f"{a.get('document_coverage', '—')} | {r.get('embedding_vs_lexical_same_set', '—')} |")
    lines += ["", "Each pilot case has 1–2 short documents, so every retriever returns all of them; this checks that "
              "retrieval works and is reproducible, not that it ranks well. Ranking quality needs the v4 test set's "
              "gold evidence annotations.", "", "## Verification decisions", ""]
    headers = ["label", "heuristics_only", "heuristics_lexical"] + [f"{c}@{m}" for m in models for c in ("gemini_no_rag", "gemini_rag", "hybrid")] + ["v3_decision"]
    lines += ["| Case | " + " | ".join(headers) + " |", "|---|" + "---|" * len(headers)]
    for case_id, row in report["decisions"].items():
        lines.append(f"| {case_id} | " + " | ".join(str(row.get(h) or "—") for h in headers) + " |")
    lines += ["", "## Disagreements between Gemini and the deterministic fallback", "",
              "Pairs: `gemini_no_rag` vs `heuristics_only` (no documents); `gemini_rag` vs `heuristics_lexical` "
              "(the production fallback when documents are present). A disagreement is a different decision or a "
              "different fraud flag (FLAG/REJECT or any red flag).", ""]
    if report["disagreements"]:
        lines += ["| Model | Case | Label | Gemini config → decision (flagged, red flags) | Fallback → decision (flagged) |",
                  "|---|---|---|---|---|"]
        for d in report["disagreements"]:
            lines.append(f"| {d['model']} | {d['case_id']} | {d['label']} | {d['gemini_config']} → {d['gemini_decision']} "
                         f"({d['gemini_flagged']}, {d['gemini_red_flags']}) | {d['fallback_config']} → "
                         f"{d['fallback_decision']} ({d['fallback_flagged']}) |")
    else:
        lines.append("None among the configurations that completed.")
    lines += ["", f"Offline configurations reproduced identically across the two runs: **{report['offline_reproducible']}**.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-a", default="gemini_pilot_v3")
    parser.add_argument("--run-b", default="gemini_pilot_v3_model_3_6")
    parser.add_argument("--pre-run-freeze", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    a, b = load(args.run_a), load(args.run_b)
    if a["plan"]["case_ids"] != b["plan"]["case_ids"]:
        raise SystemExit("The two experiments did not use the same case IDs")
    model_a, model_b = a["plan"]["model"], b["plan"]["model"]
    dataset = {json.loads(l)["case_id"]: json.loads(l) for l in Path(a["plan"]["dataset"]).read_text().splitlines() if l.strip()}
    cases = {i: dataset[i] for i in a["plan"]["case_ids"]}
    pre = json.loads(args.pre_run_freeze.read_text())
    post = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in pre["files"]}
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "case_ids": list(cases),
              "freeze": {"git_head": pre["git_head"], "working_tree_clean_before": pre["working_tree_clean"],
                         "files_hashed": len(post), "identical": post == pre["files"],
                         "git_head_after": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                                          cwd=ROOT).stdout.strip()},
              "models": {}, "gemini_api_calls_made_by_this_script": 0}
    runs = {model_a: a, model_b: b}
    for model, run in runs.items():
        generation = generation_stats(run)
        latencies = [v for c in API for v in generation[c]["success_latency_seconds"]["values"]]
        report["models"][model] = {"experiment": run["experiment"], "calls": {"generation": run["state"]["calls_this_run"].get("generation", 0),
                                                                              "embedding": run["state"]["calls_this_run"].get("embedding", 0)},
                                   "generation": generation, "stopped_reason": run["state"]["stopped_reason"],
                                   "all_success_latency": {"n": len(latencies),
                                                           "mean": round(statistics.mean(latencies), 2) if latencies else None,
                                                           "p95_nearest_rank": round(nearest_rank(latencies, .95), 2) if latencies else None,
                                                           "values": sorted(latencies)}}
    report["retrieval"] = retrieval_comparison(a, b, cases)
    report["decisions"] = decisions(runs, cases)
    report["disagreements"] = disagreements(runs, cases)
    report["offline_reproducible"] = offline_reproducible(a, b)
    target = args.output_dir or RUNS / f"gemini_model_comparison_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    target.mkdir(parents=True, exist_ok=False)
    (target / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (target / "report.md").write_text(render(report))
    print(target)
    return report


if __name__ == "__main__":
    main()
