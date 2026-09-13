# Token usage and cost report

Final full-dataset run that produced `output.csv`, `dataset/output.csv`.

| Field | Value |
|---|---|
| Run started (UTC) | 2026-09-13 03:59:21 |
| Provider | openai |
| Models used | gpt-5.4-2026-03-05 |
| Evaluation requests | 250 |
| Requests answered without any model call | 50 |
| Requests with at least one model call | 200 |
| Total model calls | 200 |
| Input tokens | 395,043 |
| Output tokens | 43,242 |
| Total tokens | 438,285 |
| Average tokens per request | 1,753.1 |
| Estimated total cost (USD) | $0.9262 |
| Estimated cost per request (USD) | $0.003705 |

Pricing assumption: $1.25 per million input tokens and $10.00 per million output tokens.

## Per model

| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---:|---:|---:|---:|---:|
| openai | gpt-5.4-2026-03-05 | 200 | 395,043 | 43,242 | 438,285 | $0.9262 |

## Per purpose

| Purpose | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---:|---:|---:|---:|---:|
| evidence_interpretation | 200 | 395,043 | 43,242 | 438,285 | $0.9262 |

Deterministic forecasting, plan generation, ranking and output validation use no tokens. The model is called only to interpret supplied messages and images, so requests with no such evidence cost nothing.

No API keys, credentials or configuration values are recorded here.
