"""Local demonstration of the hybrid v4 fraud-verification prototype (offline; no API key, no network).

    python evaluation/final_evaluation/demo.py                 # four illustrative scenarios
    python evaluation/final_evaluation/demo.py FE-FS-MED-02    # any scenario ID from scenarios.jsonl

For each scenario: the automated decision and its explanation, then the SIMULATED independent confirmations
(beneficiary, institution, payment destination, amount), the final state, and the audit-chain check.
Gemini answers are scripted and confirmations are simulated: this demonstrates the workflow logic only.
"""
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_final_evaluation as fe  # noqa: E402

DEFAULT = ["FE-LC-MED-03", "FE-FS-MED-02", "FE-LI-MED-01", "FE-FD-EDU-05"]
WHY = {"FE-LC-MED-03": "genuine campaign raising only the balance after insurance",
       "FE-FS-MED-02": "consistent but inflated estimate (only the hospital's billing desk reveals it)",
       "FE-LI-MED-01": "genuine patient at a government hospital with no formal quotation",
       "FE-FD-EDU-05": "bank details substituted in one of the documents"}


def show(case_id: str, scenarios: dict) -> None:
    s = scenarios[case_id]
    with fe.NetworkGuard():
        row = asyncio.run(fe.run_one(s))
    v4 = row["systems"]["hybrid_v4"]
    c = v4["confirmation"]
    print("=" * 100)
    print(f"{case_id}  [{s['stratum']}, truth: {s['truth_label']}]  {s['input']['title']}")
    if case_id in WHY:
        print(f"Why it is shown: {WHY[case_id]}")
    print(f"Goal Rs {s['input']['goal_amount']:,}; submitted {s['input']['submitted_on']}; scripted Gemini: "
          f"{row['gemini']['script']} -> {row['gemini']['status']}")
    print("-" * 100)
    print(v4["explanation"])
    print("-" * 100)
    print(f"Other systems on the same input: frozen V3 {row['systems']['v3_frozen']['decision']} -> "
          f"{row['systems']['v3_frozen']['confirmation']['end_state']}; hybrid v2 {row['systems']['hybrid_v2']['decision']} -> "
          f"{row['systems']['hybrid_v2']['confirmation']['end_state']}; hybrid v3 {row['systems']['hybrid_v3']['decision']} -> "
          f"{row['systems']['hybrid_v3']['confirmation']['end_state']}")
    print(f"SIMULATED confirmation (hybrid v4): {c['initial_state']} -> {c['end_state']}"
          + ("  [assisted cost route taken]" if c["assisted_route_taken"] else ""))
    print(f"  independently confirmed: {c['independently_confirmed'] or 'none'}; pending: {c['pending_checks'] or 'none'}")
    if c["activated"]:
        print(f"  ACTIVATED; disbursement limited to Rs {c['disbursement_limit_inr']:,.0f}")
    print(f"  audit log: {c['audit_entries']} hash-chained entries, chain valid: {c['audit_chain_valid']}")


def main(argv) -> None:
    scenarios = {json.loads(l)["case_id"]: json.loads(l) for l in fe.SCENARIOS.read_text(encoding="utf-8").splitlines() if l}
    print(fe.LABEL)
    for case_id in (argv or DEFAULT):
        show(case_id, scenarios)


if __name__ == "__main__":
    main(sys.argv[1:])
