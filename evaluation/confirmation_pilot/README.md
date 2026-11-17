# Confirmation pilot log templates

Fill one row per campaign in `campaigns_template.csv` and one row per contact attempt in
`attempts_template.csv`, then score the pilot with:

    ./.venv/bin/python -B evaluation/analyze_confirmation_log.py campaigns.csv attempts.csv --output metrics.json

The analyzer replays every attempt through the development approval workflow, so the pilot is scored with
exactly the rules the system enforces. Keep the filled logs outside the repository if they contain real contact
details; only the aggregate `metrics.json` should be shared.

| Field | Values |
|---|---|
| `check` | `BENEFICIARY`, `PAYMENT_DESTINATION`, `INSTITUTION` |
| `contact_origin` | `independent` (you found it yourself), `campaign_printed` (taken from the uploads), `campaign_out_of_band` (sent by the campaigner some other way) |
| `contact_source` | `OFFICIAL_REGISTRY`, `OFFICIAL_DIRECTORY`, `PLATFORM_KYC`, `PRIOR_VERIFIED_RECORD`, `CAMPAIGN_SUPPLIED` |
| `outcome` | `CONFIRMED`, `CONTRADICTED`, `UNREACHABLE`, `INCONCLUSIVE` |
| `supplied_contact_matches_directory` | `yes` / `no`: does the institution contact the campaign supplied match the one you found independently? Blank if none was supplied |
| `label` | leave blank for real campaigns unless the outcome is later established; red-team campaigns are `fraudulent` |

Record `contact_origin` honestly even when it was a mistake — measuring how often verifiers use
campaign-supplied contacts is one of the pilot's goals.
