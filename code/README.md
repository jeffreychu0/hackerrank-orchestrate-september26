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
| `--provider anthropic` | Interpret the evidence with Claude instead of GPT |

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
| `harness/recurrence.py` | Recurring patterns; cadence recovery across gaps; income streams; lapse detection |
| `harness/forecast.py` | Dated balance path, safe amount today, earliest safe full-payment date |
| `harness/plans.py` | Candidate generation, offer eligibility, strict ranking |
| `harness/changes.py` | Permitted `stop:` / `reduce_to:` search, least intrusive first |
| `harness/decide.py` | Locks the computed output fields for one request |
| `harness/providers.py` | Provider registry, client factory and list pricing |
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
- **A payment is judged over the window the request is live in.** Plan safety and
  `earliest_date_for_full_payment` run from the request date through the later of
  `desired_completion_date` and the final payment; `amount_safe_to_pay` stays a
  90-day measure. This is the reading request_08, request_12 and request_13 follow.
- **An obligation due today is due.** A monthly commitment whose next occurrence
  lands on the request date counts, unless the history already records it as
  settled that day.
- **A one-off future row is a flow, not a pattern.** A scheduled arrears balance
  or school fee is reserved on its own date and never re-times or re-prices the
  category pattern it happens to share.
- **Determinism.** Everything except the interpretation call is a pure function
  of the dataset. The model call is the one source of run-to-run variation;
  `--no-model` removes it entirely.

## Providers

Two interpretation providers are implemented behind one contract
(`structured(...) -> (payload, ModelResult)`), selected with `--provider`:

| Provider | Package | Default model | Credentials |
|---|---|---|---|
| `openai` | `open_ai/` | `OPENAI_MODEL` | `OPENAI_API_KEY` |
| `anthropic` | `anthropic_ai/` | `claude-opus-5` | `ANTHROPIC_API_KEY`, or any credential the SDK resolves |

The Anthropic package is spelled `anthropic_ai` because `code/` is on
`sys.path`, so a local package named `anthropic` would shadow the installed SDK
- the same reason `open_ai` is spelled with an underscore. Nothing under
`harness/` imports a vendor SDK; adding a third provider is one row in
`harness/providers.py`.

Anthropic specifics: structured output goes through
`output_config.format.json_schema`; a refusal arrives as HTTP 200, so
`stop_reason` is checked before the body is parsed; thinking blocks are skipped
when reading the answer; a blank `ANTHROPIC_API_KEY` is not an error, because
the SDK then resolves `ANTHROPIC_AUTH_TOKEN`, an `ant auth login` profile or
workload identity federation. Cost estimates are per model, not per provider.

### Provider comparison

```powershell
python code/compare_providers.py            # runs both, scores both, diffs them
python code/compare_providers.py --reuse    # re-score CSVs already on disk
```

Measured on the 25 published samples, GPT-5.4 against Claude Sonnet 5 on an
identical prompt and schema:

| | GPT-5.4 | Claude Sonnet 5 |
|---|---:|---:|
| `affordability_status` | 22/25 | 22/25 |
| `recommended_payment_method` | 23/25 | 23/25 |
| `payment_plan` | 21/25 | 21/25 |
| `earliest_date_for_full_payment` | 21/25 | 21/25 |
| `spending_changes_needed` | 22/25 | 22/25 |
| All five fields exact | 19/25 | 19/25 |
| Mean relative amount error | 0.031 | 0.033 |
| Tokens for the 19 calls | 49,208 | 89,607 |
| Estimated cost | $0.10 | $0.30 |

24 of 25 rows are byte-identical. The exception is request_19, whose grocery
receipt is cropped before its final payable total: GPT fills the blank amount
from the visible item subtotal, Claude declines to fill it and says why. The
sample answer sits between the two results. The deterministic engine decides
everything else, which is why two different models land in the same place.

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
| `affordability_status` | 21/25 | 22/25 |
| `recommended_payment_method` | 22/25 | 23/25 |
| `payment_plan` | 21/25 | 21/25 |
| `earliest_date_for_full_payment` | 20/25 | 21/25 |
| `spending_changes_needed` | 22/25 | 22/25 |
| All five fields exact | 18/25 | 19/25 |
| Mean relative error on `amount_safe_to_pay` | 0.072 | 0.031 |

## Evaluation

Two evaluations, answering different questions.

| | `evaluate_samples.py` | `evaluation/model_to_model/` |
|---|---|---|
| Question | Does it match the published answers? | Which of two independent readings of the evidence is better supported? |
| Coverage | 25 labelled requests | any request in the dataset |
| Needs ground truth | yes | no |
| Costs tokens | only with `--model` | yes, on both stages |

Results for both live in [evaluation/EVALUATION.md](evaluation/EVALUATION.md)
(identical copy at `docs/EVALUATION.md`), regenerated from the run artifacts with
`python code/evaluation/build_evaluation_md.py` so the numbers cannot drift from
the runs they describe.

The second is described in
[evaluation/model_to_model/README.md](evaluation/model_to_model/README.md): two
providers read the same evidence independently, then each grades both readings
blind. It measures its own trustworthiness as it goes - self-preference bias is
estimated from the two judging directions rather than assumed away, and the
judges are calibrated against deliberately damaged readings whose correct
verdict is known by construction.

## Tests

Offline suite — no key, no network calls, no charges:

```powershell
python -m unittest discover -s code/tests -t code -v
```

Covers money formatting, evidence scoping, recurrence and lapse detection,
forecast ordering and safety, offer eligibility, plan ranking, spending-change
permissions, claim validation (including the payroll guardrail) and every output
contract rule. `tests/test_forecast_fixes.py` pins the six forecast defects the
sample calibration exposed, one class per defect, and
`tests/test_model_to_model.py` covers the cross-model eval: blinding, the
self-preference arithmetic, and the calibration maths. `tests/test_open_ai.py` and `tests/test_tools.py` intercept HTTP
beneath the real SDK to check request shape and failure handling.

Live smoke tests (these do make paid calls):

```powershell
python code/smoke_test.py
python code/smoke_tools.py
```

## Design notes

| Document | Contents |
|---|---|
| [../docs/EXPLANATION.md](../docs/EXPLANATION.md) | What the system is and why it is split this way |
| [../docs/E2E.md](../docs/E2E.md) | What runs, in what order, and what it writes |
| [../docs/DESIGN_DECISIONS.md](../docs/DESIGN_DECISIONS.md) | Every non-obvious choice and its alternative |
| [../docs/EVALUATION.md](../docs/EVALUATION.md) | Results of both evaluations |
| [../docs/](../docs/README.md) | Deeper background: dataset, samples, images, harness |

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
| `code/evaluation/usage_report.md` | Providers, models, calls, tokens, cost (path pinned by the submission contract) |
| `code/evaluation/reports/evidence_audit.jsonl` | Per request: coverage, accepted and refused claims, unresolved questions, final fields |
| `code/evaluation/reports/model_to_model/` | Cross-model scorecards and per-item verdicts |
| `code/evaluation/EVALUATION.md` | Both evaluations, generated from the artifacts |
