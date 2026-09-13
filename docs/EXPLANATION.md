# What this is

Start here. [E2E.md](E2E.md) is what runs; [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
is why it runs that way.

## The one idea

**Code decides. The model reads.**

The LLM never produces a number that reaches `output.csv`. It reads the supplied
messages and images and returns *claims* about what they mean. Code validates
those claims, then computes every output field from them.

```
messages + images ──► model ──► claims ──► validator ──► forecast ──► output row
                    (reads)              (code)        (code)       (code)
```

## Why

The dataset gives you two different problems wearing one coat.

| Problem | Needs | Owner |
|---|---|---|
| An Indonesian payroll message says the bonus is unapproved | language, context, judgement | model |
| A receipt is cropped before its payable total | vision, judgement | model |
| Will the balance hold above INR 92,800 for 90 days? | exact arithmetic | code |
| Which of four payment options ranks first? | a published ordering | code |

Letting the model do the second pair makes the answer unreproducible and
unverifiable. Letting code do the first pair means inventing an Indonesian
payroll parser. So the split is the design.

## What the model may and may not say

It picks from a fixed vocabulary of 10 claim types — nothing else parses.

| It can say | It cannot say |
|---|---|
| "this income stream ended" | "the safe amount is 28,820" |
| "this amount is 1,037.52 from 2026-01-15" | "recommend installments" |
| "this receipt shows ₹79,679.26" | "the earliest safe date is 15 May" |
| "this evidence changes nothing" | "skip the minimum balance here" |

Every claim is checked against the data before it can move a single projected
cash flow: the source must exist, the event must belong to this user, the
category must appear in their history, the date must be in range, the amount
must parse. Two further rules carry the financial risk:

- **A claim that frees up cash is discarded unless marked `confirmed`.** Claims
  that reserve cash apply either way — the safer reading wins.
- **Payroll can only be stopped by a claim that names the exact pattern.** A note
  about an unapproved bonus cannot delete the salary it sits beside.

## Reading `output.csv`

250 rows, one per request, in dataset order.

| Column | What it is |
|---|---|
| `amount_safe_to_pay` | Most payable today without breaking the floor in 90 days, capped at the request. **Before** any optional spending cut. |
| `affordability_status` | `affordable_now` / `affordable_with_plan` / `affordable_later` / `not_affordable` |
| `recommended_payment_method` | `full_payment` / `partial_payment` / `installments` / `wait` / `not_recommended` |
| `payment_plan` | `YYYY-MM-DD:amount` joined by `\|`, or `none` |
| `earliest_date_for_full_payment` | First date one full payment is safe. Unchanged budget, ignores method preference. Empty if never. |
| `spending_changes_needed` | Up to three `stop:`/`reduce_to:`, or `none` |
| `decision_explanation` | Generated from the locked fields by template |

A row that would break any published invariant is never written; it is replaced
by the conservative `not_recommended` answer.

## Honest limits

- **Sample agreement is 19/25 exact.** The six misses are forecast-threshold
  effects — 1–3% of variable-spend estimation landing on the wrong side of a
  cutoff — not rule errors. Verified by solving for the scaling factor that
  reproduces each sample's amount; see [HARNESS.md](HARNESS.md).
- **`not_affordable` is 17% of `output.csv` vs 28% of the samples.** Could be a
  population difference or a bias 25 rows cannot reveal. Not resolvable with the
  data supplied. No threshold was tuned to close it.
- **The model call is the only non-deterministic step.** `--no-model` removes it
  entirely and still answers every request.
- **Some policy numbers are fitted to 25 samples.** They live in one dataclass so
  they can be re-swept. See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md).

## Where things are

| | |
|---|---|
| Run it | `python code/main.py` |
| The engine | `code/harness/` |
| What the model sees | `code/harness/interpret.py` |
| What code accepts from it | `code/harness/facts.py` |
| Evidence trail per request | `code/evaluation/reports/evidence_audit.jsonl` |
| Results | [EVALUATION.md](EVALUATION.md) |
