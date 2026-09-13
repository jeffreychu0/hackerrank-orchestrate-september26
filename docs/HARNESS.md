# Harness architecture: what is deterministic and what is not

This document records the division of responsibility implemented in
[`code/harness/`](../code/harness). The rules come from
[problem_statement.md](../problem_statement.md) and [AGENTS.md](../AGENTS.md);
the calibration figures come from the 25 answers in `dataset/sample_requests.csv`.

**Code guarantees evidence coverage and financial correctness. The model
interprets ambiguous evidence. The model never produces an amount, a date, a
payment method or a plan that reaches `output.csv`.**

## Flow

```mermaid
flowchart TD
    A[Select request by request_id] --> B[Code loads the mandatory evidence bundle]
    B --> C[Code reconstructs recurring patterns]
    C --> D{Messages, images or blank amounts?}
    D -- No --> G
    D -- Yes --> E[Model returns structured claims]
    E --> F[Code validates each claim]
    F --> G[Code rebuilds patterns and forecasts 90 days]
    G --> H[Code generates and tests eligible plans]
    H --> I{Any safe plan without spending changes?}
    I -- No --> J[Code searches permitted changes, least intrusive first]
    I -- Yes --> K[Code applies the strict ranking]
    J --> K
    K --> L[Explanation from locked fields]
    L --> M[Code validates the contract and writes the row]
```

## Division of responsibility

| Responsibility | Owner | Why |
|---|---|---|
| Identify request and user | Code | IDs already establish ownership; inference adds risk |
| Load profile, events, offers, messages and image metadata | Code | Missing one obligation can invalidate the recommendation |
| Interpret multilingual messages | Model | Meaning and amendments require contextual interpretation |
| Extract image amounts, separate payable from paid | Model | Receipts have varied layouts and ambiguity |
| Validate interpreted facts | Code | Unsupported changes must not enter the ledger silently |
| Apply FX, dates and monetary arithmetic | Code | Exact, repeatable calculations |
| Detect recurrence | Code proposes patterns; model flags exceptions | Repetition alone can mistake a commission or a final payroll for salary |
| Forecast balances and test plans | Code | Every payment must satisfy the same safety rules |
| Rank eligible plans | Code | The challenge defines the ordering explicitly |
| Explain the recommendation | Template by default, model optional | The published answers use one tight house style |

## Baseline evidence is always loaded

`harness/ledger.py` builds a bundle per request containing the profile, every
financial event for the user, the supplied payment options, every message known
by the request date, and the linked image metadata. Nothing depends on the model
choosing to call a tool. Unusual rows are classified rather than discarded: each
carries an explicit exclusion reason (`cancelled_transaction`,
`pending_credit_not_yet_cash`, `unrealized_valuation`, and so on) so the reason a
record did or did not count is recoverable.

The samples show why coverage has to be structural:

- `request_04`: omitting the message could turn an unapproved bonus into income.
- `request_16`: missing the receipt would omit the outstanding rent balance.
- `request_20`: reading only the main bill would miss the late-payment amount.
- `request_12`: capacity to pay in full does not authorise full payment.

## The model returns claims, not ledger edits

`harness/interpret.py` sends one JSON-schema-constrained turn per request with
evidence to read, and gets back claims in a fixed vocabulary
(`income_stream_ends`, `income_amount_change`, `income_date_change`,
`recurring_expense_amount_change`, `new_recurring_expense`, `exclude_projection`,
`event_amount`, `exclude_event`, `no_material_effect`).

`harness/facts.py` checks ownership, schema, dates, categories, amounts and
source existence before any claim can move a flow. Those checks cannot prove the
model read a message correctly, so two further rules carry the financial risk:

- **A cash-increasing claim is discarded unless it is marked confirmed.** A
  confidence score never authorises unsupported income. Claims that reserve cash
  apply either way, which is the financially safer reading.
- **Employment income can only be stopped by a claim that names the pattern and
  is scoped to the stream.** A note about an unapproved bonus or a one-off
  arrears line beside a normal payslip cannot delete the salary.

Unresolved questions stay visible in `code/evaluation/evidence_audit.jsonl`
alongside every refused claim and its refusal reason.

## Model calls are earned, not routine

`needs_model` skips the call entirely when a request has no message, no image and
no blank amount. On the evaluation set that is 50 of 250 requests, which cost no
tokens at all. The remaining 200 take one call each.

## The prompt is not the workflow

The earlier tool-loop agent enforced its workflow only through instructions: the
loop accepted final text whenever the model stopped calling tools, without
establishing that every event page had been read or that a forecast had passed.
In the harness the sequence is code, so the guarantees hold regardless of what
the model does — including doing nothing, which is what a degraded request falls
back to.

## Calibration

`code/evaluate_samples.py` scores the harness against the published answers
(read for scoring only; the solution never sees those columns).

| Field | Deterministic | With interpretation |
|---|---:|---:|
| `affordability_status` | 19/25 | 20/25 |
| `recommended_payment_method` | 20/25 | 21/25 |
| `payment_plan` | 20/25 | 20/25 |
| `earliest_date_for_full_payment` | 15/25 | 16/25 |
| `spending_changes_needed` | 21/25 | 21/25 |
| All five fields exact | 15/25 | 16/25 |
| Mean relative error on `amount_safe_to_pay` | 0.079 | 0.048 |

Policy choices that the samples drove, all in `RecurrencePolicy` so they stay
inspectable: a pattern needs two occurrences; the per-occurrence estimate is the
mean; a pattern whose last occurrence is more than 1.5 periods stale has lapsed
and is not projected; payroll wordings collapse into one income stream while
bonuses, gig payouts and a second household income stay separate; same-day
credits land before debits.
