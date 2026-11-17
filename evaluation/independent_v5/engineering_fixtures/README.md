# Engineering fixtures (NOT independent test data)

Synthetic cases written by the developer's assistant to test the v5 validator, runner and scorer offline.
Every ID starts with `ENG-`. The runner refuses them in a live run, the validator refuses them under the full
profile, and `exclusion_registry.json` lists them so their text can never enter the independent test.
The participants and labels here are fictional engineering placeholders, not real people.
Regenerate with `python evaluation/prepare_independent_data_v5.py make-engineering-fixtures`.
