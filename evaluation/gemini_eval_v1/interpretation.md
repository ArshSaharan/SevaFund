### Interpretation

*Written after reviewing the machine-generated sections above. The sample has 10 cases, one per scenario
group, so every statement below is a diagnostic observation and not an accuracy estimate.*

**Reliability.**
- 19 of 20 generation calls succeeded (Wilson 95% interval 76–99%). The one failure was a single HTTP 503,
  with no timeouts. That is much better than 3.8 Flash in the earlier pilot (1/6), but it does not yet
  establish the ≥95% success rate the go criterion requires.
- Latency roughly doubled compared with the 3-case pilot: a mean of 45.5 s and a p95 of 72.5 s, against
  21.9 s and 30.0 s. That is too slow for a synchronous check during campaign submission. It would be
  workable only as an asynchronous background check.

**Grounded contributions from documents.**
- Document-grounded Gemini moved four cases in the correct direction compared with Gemini without
  documents: V3T-244, V3T-154, V3T-044 and V3T-224. No case moved the other way.
- Without documents, Gemini returned NEEDS_MORE_INFORMATION for all 10 cases.
- Its explanations cite the retrieved evidence. On V3T-244 it found that the "unpaid" invoice was already
  paid and the supplier account closed, a contradiction frozen V3 missed (V3 sent the case for more
  information instead). On V3T-044 it found the ledger was in a different patient's name, which V3 also
  caught.
- By its own decision, Gemini + RAG flagged **no** legitimate campaign and approved no fraudulent or
  borderline campaign. It returned one rejection (V3T-244), which the combined design caps at manual
  review.

**What Gemini did not do.**
- **The internally consistent fabricated dossier (V3T-064) was not detected.** Gemini asked for more
  information, citing an alleged "future date (07 September 2026)", a missing diagnosis and an
  unfamiliar hospital.
  - The date flag is spurious: the production prompt gives the model no current date.
  - The other two flags are generic.
  - Nothing in the dossier reveals the fabrication, so this remains the case only external confirmation
    can settle.
- One retrieval check (V3T-104) failed with a 503 and was not retried, because the budget was fully used.
  A deployed combined system would treat that as a verification error and never as an approval.

**The combined system's 4/4 recall comes partly from its escalation rule, not only from detection.**
- The frozen rule escalates to manual review whenever Gemini attaches any red flag, even to an
  information request. Five of its six escalations beyond V3 came from red flags alone:
  - one fabricated-fraud case, caught for partly spurious reasons;
  - the two borderline cases, which were appropriate to escalate since V3 had approved both;
  - two legitimate campaigns.
- One of those legitimate escalations (V3T-024) rests on a real flaw in the synthetic data. The generator
  swapped a coastal story onto a landlocked city, and Gemini noticed. It is counted as a false positive
  against the label, but it is a defect in the data rather than the model.
- Net effect against frozen V3:
  - unsafe approvals of fraudulent or borderline cases fell from 3 to 0;
  - legitimate escalations rose from 0 to 2;
  - manual reviews rose from 2 to 8 of 10.

That is a large workload increase for a small sample.

**The deterministic fallback remains weak.** The production fallback (heuristics with lexical retrieval)
approved two fraudulent cases (V3T-064, V3T-044) and escalated two legitimate ones.

### Recommendation

**Gemini 3.6 Flash merits a larger evaluation, but not the full 180-call run as currently configured, and
not a production change.** Grounded detection of a contradiction V3 missed, no Gemini-initiated
escalation of legitimate campaigns, and correct use of retrieved documents justify further testing.
Three issues should be settled first, each needing the owner's decision:

1. **Pre-register the combined escalation rule.**
   - The current rule escalates on any Gemini red flag.
   - A post-hoc alternative escalates only on Gemini's FLAG or REJECT, and otherwise downgrades to
     NEEDS_MORE_INFORMATION; it would not approve when Gemini asks for more information.
   - Re-reading the saved outputs suggests this alternative would keep zero unsafe approvals and zero
     legitimate escalations at 3/4 recall. **That is a hypothesis formed after seeing these results**, so
     it must be fixed in advance and tested on new cases, not scored on these ones.
2. **Decide whether the evaluation may use a prompt that states the current date.** This changes the
   production prompt path, so the owner must approve it. Without the date, any document dated after the
   model's internal "now" can draw a spurious flag.
3. **Run the next stage on cases that have not been inspected,** preferably an early tranche of the
   protocol v4 independent set, as an asynchronous check with latency recorded. The 300-case synthetic
   corpus has now been used for V3 development, the final test, two pilots and this evaluation.

**Keep the production default model unchanged** until a pre-registered evaluation on new cases confirms
reliability (≥95% success) and acceptable latency. Keep the independent-confirmation requirement in every
configuration: none of these results justify activating a campaign or releasing funds on model judgement
alone.
