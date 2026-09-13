# Design decisions

Every non-obvious choice, what it was chosen over, and why. Context in
[EXPLANATION.md](EXPLANATION.md); the flow is in [E2E.md](E2E.md).

## Architecture

| Decision | Rejected | Why |
|---|---|---|
| Code computes every output field; the model only interprets evidence | Model produces the decision, prompt enforces the rules | A prompt-enforced workflow accepts whatever text comes back. Nothing establishes that the forecast passed. |
| Model returns claims in a 10-type vocabulary | Free-form ledger edits | Claims can be validated against the data; prose cannot. |
| Evidence loaded up front, never on model request | Tool-calling agent fetches what it wants | A missed obligation invalidates the recommendation. Coverage must be structural, not discretionary. |
| One structured call per request | Bounded tool loop for investigation | The loop cost more and added nothing the pre-loaded bundle lacked. The tool agent still exists at `code/agent.py` for exploration, not for `output.csv`. |
| No model call when there is no message, image, or blank amount | Call for every request | 50 of 250 requests have nothing to read. |
| Explanations from a template by default | Model writes the prose | The 25 sample explanations follow one tight house style; a template reproduces it exactly and cannot contradict the computed numbers. |
| Provider behind one interface (`harness/providers.py`) | Hard-code OpenAI | A second provider is a row in a table, and nothing in `harness/` imports a vendor SDK. |

## Trust boundaries

| Decision | Why |
|---|---|
| A cash-**increasing** claim is discarded unless `certainty == "confirmed"`; cash-reducing claims apply either way | The asymmetry is the point. The safer reading wins when the model is unsure. |
| Payroll can only be suppressed by a claim that names the exact pattern via `event_ids` | Found the hard way: a note about an unapproved bonus deleted the whole salary. |
| A claim scoped `single_event` can never suppress a whole pattern | A one-off arrears line beside a normal payslip is not a reason to touch the payslip. |
| Message text, image pixels and event descriptions stay in the user turn, never the system channel | Embedded instructions are data. Role separation alone isn't proof, which is why validation sits behind it. |
| Refused claims are recorded with the reason, not silently dropped | The audit trail has to show what was rejected and why. |

## The forecast

| Decision | Rejected | Why |
|---|---|---|
| `amount_safe_to_pay` = worst projected drawdown against the floor over 90 days | Balance minus minimum | Reverse-engineered from the samples; the naive version is wrong on 22 of 25. |
| Plan safety and `earliest_date_for_full_payment` judged over the **completion window** (request date → later of deadline and final payment); `amount_safe_to_pay` stays a 90-day measure | Full horizon for everything | Tested six window rules against the samples: 105 field matches vs 93. Applying the window to the amount too made it worse (0.083 vs 0.074). |
| Same-day credits land before debits | Debits first | A salary credited on payday funds that day's obligations. Fixed 5 date mismatches. |
| An obligation due **on** the request date counts, unless history already records it settled that day | Skip the request date | Cost request_19 a full month of rent. Every projected date is after the last recorded one, so nothing double-charges. |
| Cadence recovered when gaps are near-whole multiples of the smallest | Median gap | Two months of unpaid leave gives gaps `[31, 91]`; median 61 falls outside the recurring range and the salary vanishes. 8 requests had no income at all. |
| Only confirmed future **credits** extend a pattern; future debits stay standalone flows | All scheduled rows extend patterns | A scheduled "Outstanding rent balance" re-timed and re-priced the rent pattern. |
| Payroll wordings collapse into one income stream; bonus, gig, freelance, windfall, reimbursement stay separate | Group all credits by category | Only separate streams can stop or be excluded independently. Grouping by exact wording instead fragments a freelancer's income into unprojectable singletons. |
| Income the history cannot establish can be created by a confirmed claim (`new_recurring_income`) | History only | 6 requests had one prorated payslip plus a message stating the real amount and date. It is cash-increasing, so it needs `confirmed`. |

## Plans and changes

| Decision | Why |
|---|---|
| Ranking is a literal tuple transcribed from the statement: on-time → no cuts → cost → earlier start → fewer payments → lowest option id | Strict ordering, not a weighted score. A weighted score lets cost outvote "no cuts", which the statement forbids. |
| Spending changes are searched whenever the best no-change plan finishes **late**, then ranked against it | Completing on time outranks avoiding a cut. Searching only when no plan exists at all skips that comparison. |
| Cuts tried least-intrusive first, feasibility proven by full re-forecast | Matches the samples exactly (`stop` the ₹11 backup + `reduce` streaming, rather than stopping the ₹47 streaming). A shortfall-vs-monthly-saving comparison misses that savings must land before the binding trough. |
| `wait` is eligible whenever full payment becomes safe later, even past the deadline | The statement attaches no deadline test to `wait` eligibility; a late plan ranks last rather than being dropped. |
| A contract-invalid row is replaced by the conservative answer | Never emit an invalid row. |

## Calibrated numbers

Fitted to 25 samples, so treat as tuned rather than derived. All in
`RecurrencePolicy` / `SAFETY_WINDOW` so they can be re-swept with
`evaluate_samples.py`.

| Knob | Value | Note |
|---|---|---|
| `min_occurrences` | 2 | |
| `amount_estimator` | `mean` | |
| `stale_periods` | 1.5 | Older than this and the pattern has lapsed |
| `max_period_days` | 40 | |
| `monthly_period_range` | 26–33 | Anchors to day-of-month |
| `safety_window` | `completion` | |
| `explicit_row_handling` | `window` (±3 days) | `add` / `substitute` were within noise |
| `income_stability` | `off` | Deliberately inert — tested, hurt results |
| `variable_estimator` | `""` | Deliberately inert — every estimator above the mean left field agreement flat and worsened the amount error |

Two hypotheses **ruled out by measurement**, not argument: projected debits track
the previous 90 days of settled debits to within 1.3%, so the expense model is
unbiased; and the statement's "forecast conservatively" instruction does not pay
off on this data.

## Evaluation

| Decision | Why |
|---|---|
| A second eval that needs no ground truth | 25 labelled rows is a small target, and agreeing with them is not the same as being right. |
| Judges are blind, order-randomised per request, and run in **both** directions | Bidirectional judging turns self-preference from an assumption into a measurement. |
| `equivalent` and `neither` are first-class verdicts | A forced binary choice invents winners. |
| Judges calibrated against **injected** defects | Cross-examination cannot validate itself. The providers agree on 24 of 25 sample rows, so ground-truth calibration has almost no discriminating items. |
| The injected defects are the ones code cannot catch | `facts.py` already refuses unknown sources and invented categories. Nothing in code can tell that `next_occurrence` was quietly promoted to `ongoing`. |
| EVALUATION.md is generated from artifacts | Two copies of a hand-written report drift. Numbers cannot disagree with the run that produced them. |

## Known weak points

| | |
|---|---|
| English keyword tables decide income-stream identity and terminal income (`"final "`, `"terminated"`, …) | String matching, not analysis, on the income side of the ledger. Moving terminal-income detection into the claim vocabulary is the next change. |
| The policy table is fitted to 25 samples | Over-tuning risk; knobs are isolated and re-sweepable. |
| The judge calibration set is small and synthetic | Measures sensitivity to defects chosen in advance, not unknown ones. |
| Judges share a blind spot with producers | A fact both readings miss and neither judge flags is invisible to the method. |
