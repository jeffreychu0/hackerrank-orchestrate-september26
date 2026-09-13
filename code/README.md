# Buy or Wait? — solution code

A deterministic financial decision harness with bounded model interpretation.

Code owns every number: evidence retrieval, currency conversion, recurrence
reconstruction, the 90-day forecast, plan generation, the challenge's ranking
order and output validation. The model is used for exactly one thing — reading
the supplied multilingual messages and image documents and returning structured
claims about what they mean. Those claims are validated before they can move a
single projected cash flow, and 50 of the 250 evaluation requests carry no such
evidence at all, so they cost no tokens.

## Setup

Python 3.10+ (verified on 3.14). From the repository root:

```powershell
python -m venv code/.venv
code/.venv/Scripts/python -m pip install -r code/requirements.txt
Copy-Item code/.env.example code/.env
```

On macOS/Linux use `code/.venv/bin/python` and `cp code/.env.example code/.env`.
Do not overwrite an existing configured `.env`.

Edit `code/.env`:

```dotenv
OPENAI_API_KEY=your_actual_api_key
OPENAI_MODEL=gpt-5.4
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
OPENAI_MAX_OUTPUT_TOKENS=2048
```

The key and model are required; the rest have the defaults shown. Secrets are
read from the environment or `code/.env` only, and are never printed or written
to any output file.

## Run

```powershell
python code/main.py
```

That reads `dataset/`, writes predictions to `output.csv` in the repository root
and to `dataset/output.csv`, and writes `code/evaluation/usage_report.md` plus a
per-request evidence trail at `code/evaluation/evidence_audit.jsonl`.

Useful flags:

| Flag | Effect |
|---|---|
| `--no-model` | Fully deterministic pass; no API calls, no tokens, no cost |
| `--request-id request_07` | Run one request (repeatable); sample ids are allowed |
| `--dry-run --verbose` | Print every produced row without touching `output.csv` |
| `--explain model` | Have the model word the explanation from locked fields |
| `--workers 8` | Parallel requests when the model is in use |
| `--input-cost-per-mtok` / `--output-cost-per-mtok` | Pricing used in the usage report |
| `--no-mirror` | Skip the `dataset/output.csv` copy |

A model failure on one request degrades that request to the deterministic path
and is reported on stderr; it never aborts the run. A row that would break the
output contract is replaced by the conservative `not_recommended` answer rather
than being written out invalid.

## How a request is answered

```text
load the full evidence bundle          code   every event, option, message, image
detect recurring patterns              code   income streams, commitments, variable essentials
read messages and images               model  returns claims, never ledger edits
validate the claims                    code   source, ownership, category, date, amount
rebuild patterns and forecast 90 days  code   exact decimal arithmetic, dated FX
generate and test candidate plans      code   every payment checked against the same floor
search permitted spending changes      code   least intrusive first, re-forecast to prove it
rank by the challenge ordering         code   deadline, no changes, cost, start, count, option id
write and validate the row             code   contract enforced before anything is written
```

### Modules

| File | Responsibility |
|---|---|
| `harness/ledger.py` | Mandatory evidence bundle; cash effects with provenance and exclusion reasons |
| `harness/recurrence.py` | Recurring patterns; income-stream identification; lapsed-pattern detection |
| `harness/forecast.py` | Dated balance path, safe amount today, earliest safe full-payment date |
| `harness/plans.py` | Candidate generation, offer eligibility, strict ranking |
| `harness/changes.py` | Permitted `stop:` / `reduce_to:` search, least intrusive first |
| `harness/decide.py` | Locks the computed output fields for one request |
| `harness/interpret.py` | The model prompt, JSON schema and image attachment |
| `harness/facts.py` | Claim vocabulary, validation and application |
| `harness/explain.py` | Explanation writers (deterministic template, optional model) |
| `harness/output.py` | Output-contract validation and CSV writing |
| `harness/runner.py` | Orchestration, degradation handling, audit trail |
| `harness/usage.py` | Token and cost accounting for `evaluation/usage_report.md` |

### Decisions worth knowing

- **The balance is a snapshot, not a replay.** Settled history shapes patterns;
  it is never re-deducted from `current_available_balance`.
- **Same-day credits land before debits.** A salary credited on payday funds
  that day's obligations, which is how the supplied samples read.
- **Capacity fields ignore optional cuts.** `amount_safe_to_pay` and
  `earliest_date_for_full_payment` are always measured on the unchanged budget,
  even when the recommended plan depends on a spending change.
- **Payroll cannot be deleted by a vague claim.** Suppressing an employment
  income stream requires a claim that names the pattern and is scoped to the
  stream, so a note about an unapproved bonus cannot erase the salary.
- **Cash-increasing claims need confirmation.** A claim that frees up money is
  discarded unless the evidence states the fact as settled or approved; claims
  that reserve money are applied either way, which is the safer reading.
- **Determinism.** Everything except the interpretation call is a pure function
  of the dataset. The model call is the one source of run-to-run variation;
  `--no-model` removes it entirely.

## Calibrating against the supplied samples

```powershell
python code/evaluate_samples.py            # deterministic only
python code/evaluate_samples.py --model    # with evidence interpretation
```

This reads the answer columns of `dataset/sample_requests.csv` for scoring only.
The solution itself never sees them: `DatasetStore` strips those columns when
sample rows are loaded as inputs.

Current agreement with the 25 published answers:

| Field | Deterministic | With interpretation |
|---|---:|---:|
| `affordability_status` | 19/25 | 20/25 |
| `recommended_payment_method` | 20/25 | 21/25 |
| `payment_plan` | 20/25 | 20/25 |
| `earliest_date_for_full_payment` | 15/25 | 16/25 |
| `spending_changes_needed` | 21/25 | 21/25 |
| All five fields exact | 15/25 | 16/25 |
| Mean relative error on `amount_safe_to_pay` | 0.079 | 0.048 |

## Tests

Offline suite — no key, no network calls, no charges:

```powershell
python -m unittest discover -s code/tests -t code -v
```

Covers money formatting, evidence scoping, recurrence and lapse detection,
forecast ordering and safety, offer eligibility, plan ranking, spending-change
permissions, claim validation (including the payroll guardrail) and every output
contract rule. `tests/test_open_ai.py` and `tests/test_tools.py` intercept HTTP
beneath the real SDK to check request shape and failure handling.

Live smoke tests (these do make paid calls):

```powershell
python code/smoke_test.py
python code/smoke_tools.py
```

## Other entry points

- `code/prompt_cli.py` — single-turn prompt CLI over the Responses API.
- `code/agent.py` — request-scoped tool agent for interactive evidence
  exploration; see [tools/README.md](tools/README.md). It produces draft
  analysis and is not used to produce `output.csv`.

## Submission artifacts

| Path | Contents |
|---|---|
| `output.csv` | Predictions for all 250 evaluation requests |
| `dataset/output.csv` | The same predictions in the supplied template |
| `code/evaluation/usage_report.md` | Providers, models, calls, tokens, cost |
| `code/evaluation/evidence_audit.jsonl` | Per request: coverage, accepted and refused claims, unresolved questions, final fields |
