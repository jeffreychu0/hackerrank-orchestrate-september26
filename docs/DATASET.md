# Dataset guide: what one user request gives us

This document describes the participant-facing files in this checkout, inspected on September 12, 2026. Rules come from [problem_statement.md](../problem_statement.md) and [AGENTS.md](../AGENTS.md); counts and examples come from `dataset/`. No organizer-only data was used.

**A request can immediately retrieve a balance, safety threshold, preferences, transaction history, seller offers, and supporting evidence. It cannot retrieve a complete recurring budget or a ready-made affordability decision. Those must be constructed from the supplied evidence.**

## 1. Inventory and coverage

Paths below are relative to the repository root. Counts exclude CSV headers.

| File | Rows | Purpose |
|---|---:|---|
| `dataset/requests.csv` | 250 | Evaluation requests requiring predictions |
| `dataset/sample_requests.csv` | 25 | Public examples with completed output fields; format and decision-style guidance only |
| `dataset/financial_profiles.csv` | 275 | One financial profile per supplied user |
| `dataset/financial_events.csv` | 25,342 | Historical transactions, future commitments, cash-state records, and investment records |
| `dataset/request_payment_options.csv` | 790 | Two to four offers per request, including sample requests |
| `dataset/exchange_rates.csv` | 134 | Fixed rates keyed by date and conversion direction |
| `dataset/messages.csv` | 215 | User-, request-, or event-related financial evidence |
| `dataset/images.csv` | 16 | Metadata linking PNG evidence to users, requests, and events |
| `dataset/media/images/` | 16 PNGs | Documents containing financial information, including missing event amounts |
| `dataset/output.csv` | **Absent** | Specification describes a blank template, but it is missing in this working tree |

The evaluation file has 250 distinct users and the sample file has 25 distinct users. Each user has 56–129 financial-event rows. Evaluation request dates range from **2023-01-20 to 2026-09-04**; event dates across the entire dataset range from **2019-03-09 to 2026-09-03**. Evaluate each request relative to its own `request_date`, not the hackathon date or today's date. A global date range is not an individual user's history window.

## 2. Retrieval starting from one request

| Retrieve | Join/filter | What becomes available |
|---|---|---|
| Request | `requests.request_id = selected request_id` | Amount, date, deadline, request category, partial-payment permission, question |
| Profile | `financial_profiles.user_id = request.user_id` | Home currency, available balance, reserve floor, priorities, permissions |
| Events | `financial_events.user_id = request.user_id` | All supplied financial history and commitments for this user |
| Payment offers | `request_payment_options.request_id = request.request_id` | Actual seller schedules and costs |
| Messages | Retrieve by `user_id`, then resolve request/event scope | Financial updates, including user-wide messages with blank `request_id` |
| Image metadata | Retrieve by `user_id`, then resolve request/event scope | Relevant image IDs and event links |
| Image contents | `dataset/media/images/<image_id>.png` | Amounts and other evidence that CSV metadata does not contain |
| Exchange rates | Event `settlement_date`, event `currency`, profile `home_currency` | Conversion of foreign-currency cash amounts |

Use `related_event_id = financial_events.event_id` for explicit message/image links. Use `linked_event_id = financial_events.event_id` to inspect an earlier record in the same transaction or investment lifecycle. Check that linked records belong to the same user.

Do not retrieve messages only by `request_id`: **87 messages have no request ID**. Likewise, **176 messages have no related event ID**; these require interpretation and may still change income or obligations. A blank link is not proof that a message is irrelevant. Preserve the distinction between user-wide evidence, evidence for this request, and evidence explicitly linked to an event; do not automatically apply another request's evidence.

Keep this initial retrieval separate from financial interpretation. Joining rows does not establish that every credit is spendable, every expense recurs, or every seller offer is acceptable.

## 3. CSV field reference

### `requests.csv`

| Field | Immediately available meaning |
|---|---|
| `request_id` | Unique evaluation request identifier |
| `user_id` | User whose profile and evidence must be retrieved |
| `request_date` | Date on which affordability is evaluated |
| `request_type` | `purchase`, `travel`, `education`, `family_transfer`, `debt_repayment`, `investment`, `housing`, `emergency_expense`, or `other` |
| `requested_amount` | Full amount requested, in the user's home currency |
| `desired_completion_date` | Deadline for completing the request |
| `allows_partial_payment` | `true`/`false`: request-level permission; user preference must also permit it |
| `request_text` | Natural-language question and context |

`sample_requests.csv` has these same fields plus the seven decision fields described in section 7. Its answers are not labels for the evaluation requests.

### `financial_profiles.csv`

| Field | Immediately available meaning |
|---|---|
| `user_id` | Profile join key |
| `home_currency` | Currency of profile balances, requests, offers, and outputs: INR, ZAR, IDR, USD, or EUR |
| `current_available_balance` | Supplied current balance; starting point for reconstruction |
| `minimum_balance_to_keep` | Balance floor that must be maintained throughout the forecast |
| `financial_priorities` | Pipe-separated priorities, such as education or emergency savings |
| `expense_categories_to_protect` | Pipe-separated categories that must be protected |
| `expense_categories_user_is_willing_to_reduce` | Categories where reductions may be considered |
| `expense_categories_user_is_willing_to_stop` | Categories where stopping spending may be considered |
| `payment_methods_user_will_consider` | Pipe-separated allowed payment methods |
| `max_installment_months` | User's installment-duration limit; blank when installments are not considered |

Category permission alone is insufficient: a change must also target an eligible recurring, flexible, non-protected event. Priorities are supplied as categories, without numeric goal amounts or a complete savings plan.

### `financial_events.csv`

| Field | Meaning and use |
|---|---|
| `event_id` | Unique record ID; also used in proposed spending changes |
| `user_id` | Owner of the event |
| `event_type` | Observed: `expense`, `debt_payment`, `subscription`, `income`, `refund`, `investment_purchase`, `investment_valuation`, `investment_sale` |
| `description` | Text useful for recognizing commitments, salary, transfers, and unusual activity |
| `category` | Spending/income grouping; must be checked against profile permissions |
| `direction` | `debit`, `credit`, or `non_cash` |
| `amount` | Amount in this row's `currency`; 16 blanks require linked image extraction |
| `currency` | Event denomination, which may differ from home currency |
| `event_date` | Date of the recorded event |
| `settlement_date` | Cash settlement date; use for dated FX and cash timing |
| `status` | Cash/lifecycle state; see below |
| `linked_event_id` | Earlier record in the same lifecycle; not automatically a duplicate |
| `flexibility` | `fixed`, `stoppable`, `reducible`, or `reducible_or_stoppable` |
| `minimum_allowed_amount` | Supplied lower bound for a reduction, where populated; blank is not permission to reduce to zero |

Observed categories: `rent`, `utilities`, `education`, `debt_repayment`, `music_subscription`, `delivery_membership`, `salary`, `groceries`, `transport`, `dining`, `shopping`, `housing`, `insurance`, `healthcare`, `entertainment`, `cloud_storage`, `streaming`, `gym`, `family_support`, `work_expense`, `investment`, and `windfall`.

| Status | Rows | Interpretation |
|---|---:|---|
| `settled` | 25,148 | Completed cash activity; historical rows inform patterns and must not simply be replayed into the supplied current balance |
| `pending` | 71 | Reserve debits; do not treat credits as available cash |
| `scheduled` | 70 | Inspect confirmed future obligations/income and settlement timing; scheduled status alone does not make uncertain income spendable |
| `cancelled` | 22 | Exclude cancelled cash flows and resolve the associated lifecycle |
| `failed` | 21 | Exclude failed transactions from realized cash flow |
| `unrealized` | 10 | Non-cash investment values, not money available to spend |

There are 58 populated lifecycle links. Distinguish a duplicate from a separate purchase, valuation, and sale: a lifecycle link alone does not decide whether money moved. Internal transfers also require interpretation, rather than counting both entries as fresh income and spending.

### `request_payment_options.csv`

| Field | Meaning |
|---|---|
| `payment_option_id` | Unique offer ID; final tie-breaker between otherwise equal plans |
| `request_id` | Associated request |
| `payment_method` | Offered method |
| `payment_amount` | Amount per listed payment |
| `number_of_payments` | Payment count |
| `first_payment_date` | Schedule start |
| `payment_frequency_days` | Days between payments; blank for the 275 single-payment offers |
| `financing_fee` | Explicit financing cost |
| `total_payable_amount` | Total cost of the offer |

65 requests have two offers, 180 have three, and 30 have four, counting samples. Construct installment dates from the supplied day interval, not an assumed calendar-month schedule. Check duration, deadline, user preference, total cost, and every payment's safety. Do not add the financing fee twice when using the supplied total. Use decimal arithmetic and validate schedule totals.

Partial payment is separately permitted by the challenge rules and **does not need a matching seller offer**. It requires both request permission and user acceptance, with exactly two payments following the specified output rules.

### `exchange_rates.csv`

| Field | Meaning |
|---|---|
| `rate_date` | Date used for the conversion |
| `from_currency` | Original event currency |
| `to_currency` | Destination home currency |
| `rate` | Multiplier: home amount = event amount × rate |

Supplied directions are EUR→ZAR, USD→EUR, USD→IDR, USD→INR, and EUR→USD. All **140 foreign-currency cash-event rows** have an exact settlement-date/direction match in this checkout. The table is not a daily rate series for every currency pair or a license to invent future rates. No live FX lookup is needed.

### `messages.csv`

| Field | Meaning |
|---|---|
| `message_id` | Evidence identifier |
| `user_id` | Associated user |
| `request_id` | Optional request scope |
| `related_event_id` | Optional direct event link |
| `sent_at` | Timestamp, including time and timezone; unlike the date-only transaction fields |
| `source_type` | `employer`, `service_provider`, `bank`, `merchant`, or `financial_service` |
| `message_text` | Financial evidence to interpret |

Messages include English and Indonesian text. Examples describe pay changes, salary delays, unconfirmed bonuses, expired seasonal work, rent increases, internal transfers, pending refunds, and unrealized investment gains. Extract the affected fact, amount/currency, effective date, certainty, and scope. A source type is not a unique sender ID; references and text may be needed to establish that two updates came from the same source.

Resolve conflicts in this order: explicit cancellation/settlement/amendment; newer record from the same source; settled evidence over estimates; financially safer interpretation if unresolved. Treat embedded instructions as untrusted data that cannot override the challenge rules.

### `images.csv` and PNGs

The four columns are `image_id`, `user_id`, `request_id`, and `related_event_id`. There is no OCR text, extracted amount, document type, or confidence column. Each image is located at `dataset/media/images/<image_id>.png`.

All 16 metadata rows have all links populated and a matching PNG; five belong to sample requests and eleven to evaluation requests. Every blank event amount has a linked image. **Blank amounts are not zero.** Extract the relevant payable/paid amount, rather than blindly taking the largest number, subtotal, tax, or item price. Preserve the image and event IDs as provenance. Image contents are untrusted evidence too.

## 4. Concrete retrieval example: `request_33`

This is an evaluation request; the following is a retrieval example, not a predicted output.

| Fact | Retrieved value |
|---|---|
| User and request | `user_33`, `request_33` |
| Request | Housing deposit of INR 118,000 on 2026-01-07 |
| Completion deadline | 2026-03-15 |
| Request allows partial payment | `false` |
| Current balance / minimum reserve | INR 167,280 / INR 102,100 |
| Priorities | `emergency_savings`, `travel` |
| Protected categories | `rent`, `insurance`, `transport` |
| May reduce | `streaming`, `shopping`, `entertainment` |
| May stop | `streaming`, `cloud_storage` |
| Accepted payment methods | `full_payment`, `partial_payment`; installments are not accepted |
| Retrieved history | 122 financial-event rows |
| Full-payment offer | `payment_option_91`: INR 118,000 on 2026-01-07 |
| Installment offer | `payment_option_92`: 18 × INR 7,473.33, every 31 days from 2026-01-07; total INR 134,519.94; financing fee INR 16,519.94 |
| Message | `message_23`: bank explains matching debit and credit as transfers between the user's accounts; no direct event link |
| Image-backed event | `event_3051`: settled grocery invoice dated 2026-01-06, amount blank in CSV; `image_06.png` visibly supplies a grand total of **INR 1,995.00** |

Immediate conclusions: the installment offer fails the user's preferences, and partial payment fails the request's permission despite being an accepted user method. The balance minus reserve is INR 65,180, but **this is not `amount_safe_to_pay`**: future commitments and the 90-day safety check still matter. The invoice amount completes historical evidence; because the event is already settled, it must not automatically be deducted again from the supplied balance.

Still needed: identify recurring obligations and income, interpret the internal-transfer message against history, forecast essential variable spending, and construct the future balance path before deciding whether or when a full payment is safe.

## 5. Missing information and derived data we need to build

“Build” here means derive a documented representation from supplied evidence, not fabricate financial facts.

| Missing or incomplete item | What the solution needs to construct or resolve |
|---|---|
| **Complete recurring budget** | A per-user schedule of supported recurring income and expenses: amount/bounds, cadence, next date, category, flexibility, and supporting event IDs. There is no budget CSV, recurrence flag, recurrence group ID, or precomputed monthly total. |
| **90-day cash-flow forecast** | Dated projected credits, reserved debits, recurring commitments, essential variable expenses, proposed payments, and running balances. A monthly aggregate alone cannot identify an unsafe day. |
| Essential variable-spending allowance | Conservative history-based estimates for groceries, transport, utilities, and other relevant essentials. No ready-made category forecast or mandated estimation formula is supplied. |
| Normalized current financial state | Resolve pending/settled/cancelled/failed records, duplicates, internal transfers, and investment lifecycles without double counting. Preserve reasons for including or excluding records. |
| Structured message amendments | Extract revised amounts/dates, cancellations, confirmation status, and effective periods. A complete amendment table is not provided. |
| Image-extracted financial fields | Recover 16 missing amounts from linked documents and validate the selected total/currency. No OCR transcript is supplied. All images exist, so this is an extraction task rather than absent evidence. |
| Full future income calendar | Infer only supported recurring income and incorporate confirmed salary dates and amendments. Do not extrapolate one-off bonuses, commissions, refunds, lottery winnings, investment gains, or expired work into guaranteed cash. |
| Allowed spending-change candidates | Intersect recurring-event flexibility with profile permissions and protected categories; respect supplied minimum amounts. Derive dated savings from eligible changes rather than assuming a category can be cut wholesale. |
| Safe payment capacity and plans | Calculate today's safe amount, earliest safe full-payment date, eligible schedules, spending changes, and explanation from the baseline and candidate forecasts. None is supplied for evaluation requests. |
| Balance snapshot metadata | Profile has no explicit balance-as-of timestamp, account breakdown, or flag saying which holds are already reflected. Document use of the balance as the request's starting state, reserve pending debits per the rules, and avoid replaying settled history. |
| Forecast conventions | Document day-boundary/intraday ordering, recurring-date handling, estimation method, and rounding. The 90-day requirement is explicit; these implementation details are not fully specified. Use conservative handling of uncertainty. |
| Quantified financial goals | Priorities exist, but numeric goal targets, goal deadlines, and a complete debt/asset inventory do not. Do not invent them or seek external banking data. |
| Output template | `dataset/output.csv` is currently absent; git reports it as deleted. Generate the required output when implementing the solution, preserving current work until then. |

A useful derived recurring-budget record would carry: category/commitment description, source event IDs, cadence, effective start/end, next due date, projected home-currency amount, protected/flexible status, minimum permitted amount, amendment evidence, and uncertainty. This is a proposed internal representation, not an existing dataset schema.

## 6. Observed completeness and parsing checks

- No duplicate primary IDs were found within the inspected request, sample, profile, event, option, message, or image files.
- No missing user/request/event references were found in the checked joins; directly linked message/image events matched their users.
- Every listed PNG exists, and every blank event amount has an image link. Only `image_06.png` was visually interpreted for this document; the other documents still need extraction during implementation.
- Ten settlement dates are blank, all on `unrealized` records. These are non-cash values, not missing salary payment dates.
- `minimum_allowed_amount` is blank on 22,435 events, and `linked_event_id` is blank on 25,284. Neither field is universally applicable.
- 119 profiles have blank `max_installment_months`; 39 have blank reducible-category lists and 62 have blank stoppable-category lists. Do not interpret empty lists as unrestricted consent.
- Seven sample answers have a blank earliest full-payment date, which is allowed when full payment is not safe within the forecast.

Read CSVs as UTF-8 with a CSV parser: quoted text can contain commas. Parse pipe-delimited lists separately, booleans explicitly, dates/timestamps appropriately, and monetary values as decimals. A CSV blank needs field-specific interpretation. Structural completeness does not mean that recurrence, message conflicts, or financial safety have already been resolved.

## 7. What the reconstructed data must support

The solution must emit exactly one row per evaluation request, using these columns in order:

```text
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
```

The baseline forecast must preserve `minimum_balance_to_keep` throughout the next 90 days. `amount_safe_to_pay` is today's maximum safe payment before optional spending changes, capped between zero and the requested amount. `earliest_date_for_full_payment` is the first safe single-full-payment date without optional changes, independent of payment-method preferences; leave it blank if none exists within the forecast.

Statuses are `affordable_now`, `affordable_with_plan`, `affordable_later`, and `not_affordable`. Methods are `full_payment`, `partial_payment`, `installments`, `wait`, and `not_recommended`. Full payment, partial payment, and installments require user acceptance; waiting requires that full payment becomes safe later and the user accepts full payment.

Plans use chronological `YYYY-MM-DD:amount` entries joined by `|`, or `none`. Partial payment requires `0 < amount_safe_to_pay < requested_amount`, both permissions, and exactly two payments: today's safe amount on the request date, then the remainder on `earliest_date_for_full_payment`, no later than the completion deadline. Validate the resulting balance path as well. Installments must match a supplied offer.

Spending changes are `none` or at most three `stop:<event_id>` / `reduce_to:<event_id>:<new_amount>` actions. Stopping and reducing the same event are mutually exclusive. Eligible plans must complete the request by its deadline and maintain the safety floor. Rank safe alternatives by deadline completion, no spending changes, lowest total cost, earlier start, fewer payments, then lowest `payment_option_id`.

These requirements explain why retrieval alone is insufficient: the missing recurring budget, resolved evidence, and daily balance forecast are necessary inputs to every decision field.
