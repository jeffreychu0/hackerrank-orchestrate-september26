# Judge calibration on injected defects

Each item pairs a real reading against the same reading damaged in one specific way. The undamaged reading is correct by construction, so a judge that cannot prefer it is not measuring evidence fidelity. These are the failure modes deterministic validation cannot catch: the validator already refuses an unknown source, an unowned event, an invented category or an impossible date.

A verdict of "equivalent" counts as a miss - the two readings are not equivalent.

| Defect | anthropic caught | openai caught | Items |
|---|---:|---:|---:|
| scope_inflation | 3/3 (100%) | 3/3 (100%) | 3 |
| amount_drift | 4/4 (100%) | 4/4 (100%) | 4 |
| scope_overreach | 5/5 (100%) | 5/5 (100%) | 5 |
| claim_omission | 5/6 (83%) | 5/6 (83%) | 6 |
| claim_invention | 6/6 (100%) | 6/6 (100%) | 6 |

## Where the misses went

| Defect | Judge | Called it equivalent | Preferred the damaged reading |
|---|---|---:|---:|
| claim_omission | anthropic | 1 | 0 |
| claim_omission | openai | 1 | 0 |

## Adjudication cost

| Judge | Calls | Tokens | Est. cost |
|---|---:|---:|---:|
| openai | 24 | 56,162 | $0.1127 |
| anthropic | 24 | 96,619 | $0.3242 |
