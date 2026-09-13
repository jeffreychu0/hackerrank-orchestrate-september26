# End to end

What actually runs. Concepts are in [EXPLANATION.md](EXPLANATION.md).

## Commands

| | |
|---|---|
| Produce `output.csv` | `python code/main.py` |
| No API calls at all | `python code/main.py --no-model` |
| One request, nothing written | `python code/main.py --request-id request_07 --dry-run --verbose` |
| Through Claude instead | `python code/main.py --provider anthropic` |
| Score against the samples | `python code/evaluate_samples.py --model` |
| Compare both providers | `python code/compare_providers.py` |
| Cross-model eval | `python code/evaluation/model_to_model/run.py --samples-only` |
| Judge calibration | `python code/evaluation/model_to_model/run.py --calibrate --reuse-runs` |
| Rebuild EVALUATION.md | `python code/evaluation/build_evaluation_md.py` |
| Tests (offline, free) | `python -m unittest discover -s code/tests -t code` |

## The pipeline, per request

| # | Stage | Owner | Module | Notes |
|---|---|---|---|---|
| 1 | Load evidence bundle | code | `ledger.py` | Every event, option, message, image for this user. Not model-requested — a missed obligation can't be blamed on a skipped tool call. |
| 2 | Detect recurring patterns | code | `recurrence.py` | Income streams, commitments, variable essentials. Cadence recovered across gaps. |
| 3 | Read messages + images | **model** | `interpret.py` | One JSON-schema call. Skipped entirely when there is nothing to read. |
| 4 | Validate claims | code | `facts.py` | Source, ownership, category, date, amount. Cash-increasing claims need `confirmed`. |
| 5 | Rebuild patterns, forecast 90 days | code | `recurrence.py`, `forecast.py` | Exact decimals, dated FX. Same-day credits land before debits. |
| 6 | Generate candidate plans | code | `plans.py` | Full / partial / installments / wait. Every payment tested on the same path. |
| 7 | Search permitted cuts | code | `changes.py` | Only when no on-time plan exists without them. Least intrusive first, proven by re-forecast. |
| 8 | Rank | code | `plans.py` | Deadline → no cuts → cost → earlier start → fewer payments → lowest option id. |
| 9 | Explain | code | `explain.py` | Template from locked fields. `--explain model` is opt-in. |
| 10 | Validate the row | code | `output.py` | Every published invariant. Failure → conservative fallback, never an invalid row. |

Stage 3 is the only non-deterministic step. If it fails, that request degrades to
the deterministic path and the run continues; the degradation is reported.

## Model call budget

| | |
|---|---:|
| Evaluation requests | 250 |
| No message, image, or blank amount → no call | 50 |
| Requests with one call | 200 |
| Calls per request | 1 |

## Artifacts a full run writes

| Path | Contents |
|---|---|
| `output.csv` | Predictions, repository root (submission) |
| `dataset/output.csv` | Same content in the supplied template |
| `code/evaluation/usage_report.md` | Provider, model, calls, tokens, cost (path pinned by the contract) |
| `code/evaluation/reports/evidence_audit.jsonl` | Per request: coverage, accepted claims, refused claims and why, unresolved questions, final fields |

## Last full run

| | |
|---|---|
| Provider / model | `openai` / `gpt-5.4-2026-03-05` |
| Rows | 250, correct order, 0 contract violations, 0 degraded |
| Tokens / cost | 449,379 / $0.94 |
| Claims accepted | 247 across 200 requests |
| Claims refused by the validator | 2 |

## Two evaluations

| | Sample check | Cross-model |
|---|---|---|
| Asks | Does it match the 25 published answers? | Which of two independent readings is better supported? |
| Needs ground truth | yes | no |
| Result | 19/25 exact on all five fields | 15/19 items had differing claims, **1** changed an output field |
| Judge reliability | n/a | 23/24 injected defects caught, per judge |

Neither feeds back into `output.csv`. Both are observational.

## Configuration

Secrets from environment or `code/.env` only; never printed, never written to an
artifact.

```dotenv
OPENAI_API_KEY=...        OPENAI_MODEL=gpt-5.4
ANTHROPIC_API_KEY=...     ANTHROPIC_MODEL=claude-opus-5
```

A blank `ANTHROPIC_API_KEY` is valid — the SDK then resolves
`ANTHROPIC_AUTH_TOKEN`, an `ant auth login` profile, or workload identity
federation.
