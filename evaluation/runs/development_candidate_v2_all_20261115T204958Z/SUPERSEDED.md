# Superseded run (robustness section only)

This run used the frozen v2 verifier (`matches_freeze_manifest: true`), so every unperturbed
metric, decision and explanation here is identical to the reported run
`development_candidate_v2_all_20261115T205042Z`.

Its **robustness** figures are invalid: the evaluation tool `evaluation/perturbations.py`
(`currency_style`) changed amounts instead of only re-formatting them
("₹1.27 lakh" -> "Rs. 1/-.27 lakh"; "₹3,65,000." -> "Rs. 3,65/-,000."). The tool was fixed and
guarded by `test_perturbations_preserve_every_rupee_amount`; the verifier was not modified.
Kept for traceability. Do not cite its robustness table.
