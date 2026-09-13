# Understanding the 25 sample answers

This document explains my reading of every supplied answer in [dataset/sample_requests.csv](../dataset/sample_requests.csv). It distinguishes directly checkable facts (preferences, payment schedules, fees, image amounts, and permitted changes) from the sample's numerical forecast results. I have not independently reproduced every daily balance or the exact safe-payment amounts. Where a date or amount needs an unstated recurrence choice or ambiguous evidence, I call that out rather than inventing a derivation.

## How the combined CSV is laid out

The first **eight columns** have the [requests.csv](../dataset/requests.csv) layout:

```text
request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text
```

The remaining **seven columns** are the answer fields:

```text
amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
```

An [output.csv](../dataset/output.csv) row has eight columns: the same request_id followed by those seven answer fields. The combined sample file contains request_id once, giving 15 columns altogether. It contains request_01 through request_25; these are public examples, distinct from the 250 evaluation requests.

## Reading the answers correctly

- `amount_safe_to_pay` is the maximum safe **today before optional spending changes**, capped at the request amount. It is not simply current balance minus the minimum, and a positive value does not guarantee a complete eligible plan.
- `earliest_date_for_full_payment` measures unchanged-budget capacity independently of payment preferences. It can be later than an actual payment enabled by cuts, or equal today when the selected method is installments. An empty field means the sample finds no safe full-payment date in the forecast.
- `affordable_with_plan` includes immediate full payment enabled by cuts, as well as partial payments and installments. `affordable_now` requires an accepted full-payment method with no necessary cuts.
- A `wait` answer in these samples includes the eventual dated full payment in payment_plan. `none` appears when no payment is recommended.
- All recommended payments must fit the full 90-day balance trajectory and finish by the deadline. A first installment smaller than today's safe amount is not a sufficient safety test for the entire schedule.
- The request, profile, and option must all permit the method. An offered installment plan is not automatically eligible. Preference restrictions explain several apparently more expensive answers.
- Changes to a historical event ID identify its future recurring expense; they are not refunds of already-settled transactions. Pending credits and unrealized investments are not available cash.

The tables below preserve every request field and every answer field, in source order. `empty` represents an empty CSV field. Financial context comes from [profiles](../dataset/financial_profiles.csv), [events](../dataset/financial_events.csv), [payment options](../dataset/request_payment_options.csv), [messages](../dataset/messages.csv), [image mappings](../dataset/images.csv), and [dated exchange rates](../dataset/exchange_rates.csv), interpreted using [problem_statement.md](../problem_statement.md).

## Sample overview

| Request | Currency / amount | Safe today (supplied) | Supplied status / method | Main lesson |
| --- | --- | --- | --- | --- |
| [request_01](#request_01) | ZAR 25,256 | 25,256 | affordable_now / full_payment | Full payment fits capacity and preference |
| [request_02](#request_02) | IDR 46,018,000 | 17,229,139.20 | affordable_with_plan / installments | Installments only eligible route; salary increase |
| [request_03](#request_03) | IDR 5,491,000 | 873,000 | affordable_later / wait | Net salary, one-off arrears, wait |
| [request_04](#request_04) | IDR 12,693,000 | 8,401,800 | affordable_later / wait | Partial allowed by request but rejected by user |
| [request_05](#request_05) | ZAR 15,488 | 737 | not_affordable / not_recommended | Final payroll and unusable long plans |
| [request_06](#request_06) | EUR 620.40 | 603.30 | affordable_with_plan / full_payment | Small cut enables payment before deadline |
| [request_07](#request_07) | INR 197,400 | 87,170.56 | affordable_with_plan / installments | Installments only; salary delay |
| [request_08](#request_08) | EUR 996.60 | 284.57 | affordable_later / wait | Reduced-pay wording and waiting |
| [request_09](#request_09) | EUR 166.61 | 166.61 | affordable_now / full_payment | Small purchase; safe amount is capped |
| [request_10](#request_10) | INR 266,700 | 12,700 | not_affordable / not_recommended | Pending platform income is not cash |
| [request_11](#request_11) | IDR 13,110,000 | 12,510,645 | affordable_with_plan / full_payment | Recurring dining reduction enables payment |
| [request_12](#request_12) | ZAR 65,164 | 65,164 | affordable_with_plan / installments | Can afford full amount but rejects full payment |
| [request_13](#request_13) | EUR 941.60 | 433.40 | affordable_later / wait | Do not assume second household income continues |
| [request_14](#request_14) | EUR 5,414.20 | 597.74 | not_affordable / not_recommended | Partial payment needs safe completion |
| [request_15](#request_15) | EUR 3,685 | 83.05 | not_affordable / not_recommended | Only accepted method prohibited by request |
| [request_16](#request_16) | INR 122,500 | 122,500 | affordable_now / full_payment | Outstanding rent balance and rent increase |
| [request_17](#request_17) | INR 274,600 | 243,849.58 | affordable_with_plan / installments | Installments only; image-derived grocery expense |
| [request_18](#request_18) | EUR 3,246.10 | 462 | affordable_later / wait | Own-account transfers are not income |
| [request_19](#request_19) | INR 39,660 | 28,820 | affordable_with_plan / partial_payment | Two-payment plan avoids installment fees |
| [request_20](#request_20) | INR 303,700 | 5,400 | not_affordable / not_recommended | Pending refund versus overdue telecom debit |
| [request_21](#request_21) | USD 1,574.40 | 1,543.35 | affordable_with_plan / full_payment | Two distinct spending changes meet deadline |
| [request_22](#request_22) | EUR 731.50 | 475.46 | affordable_with_plan / installments | Unrealized portfolio value is not cash |
| [request_23](#request_23) | ZAR 38,016 | 9,152 | affordable_later / wait | Uncredited prize cannot fund repayment |
| [request_24](#request_24) | INR 109,600 | 13,420 | not_affordable / not_recommended | Settled prize is one-off and already in balance |
| [request_25](#request_25) | IDR 60,496,000 | 1,425,000 | not_affordable / not_recommended | Dated FX conversion and no eligible long plan |

## request_01

**Full payment fits capacity and preference.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_01 |
| user_id | user_01 |
| request_date | 2024-03-03 |
| request_type | purchase |
| requested_amount | 25256 |
| desired_completion_date | 2024-03-20 |
| allows_partial_payment | true |
| request_text | Would paying for the laptop today leave enough for my regular expenses? The laptop I'm looking at is ZAR 25,256. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 25256 |
| affordability_status | affordable_now |
| recommended_payment_method | full_payment |
| payment_plan | 2024-03-03:25256 |
| earliest_date_for_full_payment | 2024-03-03 |
| spending_changes_needed | none |
| decision_explanation | Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available over the next 90 days. |

**Financial context.** Current balance: ZAR 58,481.10; minimum to keep: ZAR 18,000. Accepted methods: full_payment. Installment limit: blank (no installment consent). Protected categories: rent, education, groceries, debt_repayment.

**Why I read the answer this way.** The user accepts only full_payment. The sample caps today's safe amount at the entire laptop price, so paying immediately satisfies both capacity and preference. The current balance after paying is ZAR 33,225.10, above the ZAR 18,000 reserve; that immediate subtraction is necessary but does not by itself prove 90-day safety.

History includes only a prorated first salary (event_25, ZAR 12,826), while event_103 explicitly confirms ZAR 23,320 for 15 March. Use the confirmed full salary rather than extrapolating the prorated amount. Reserve event_102, a ZAR 567.60 pending fuel authorization. The cancelled authorization event_100 is not an additional debit, and settled reversal event_99 must not be added again to the current balance. The sample says the remaining expenses also fit the reserve. Long installment offers are both unaccepted and unnecessary.

**Payment arithmetic checked.** The dated payment(s) total ZAR 25,256, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_02

**Installments only eligible route; salary increase.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_02 |
| user_id | user_02 |
| request_date | 2025-08-05 |
| request_type | travel |
| requested_amount | 46018000 |
| desired_completion_date | 2025-10-10 |
| allows_partial_payment | false |
| request_text | The current quote for the trip is IDR 46,018,000. I need to complete it by 10 October 2025. Can I afford the full trip without putting upcoming bills at risk? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 17229139.2 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | installments |
| payment_plan | 2025-08-08:15952906.67&#124;2025-09-07:15952906.67&#124;2025-10-07:15952906.67 |
| earliest_date_for_full_payment | 2025-09-15 |
| spending_changes_needed | none |
| decision_explanation | Use 3 installments of IDR 15,952,906.67, starting 8 August 2025. This leaves at least IDR 29,158,400 available. |

**Financial context.** Current balance: IDR 60,383,889.20; minimum to keep: IDR 29,158,400. Accepted methods: partial_payment, installments. Installment limit: 7. Protected categories: housing, utilities, education.

**Why I read the answer this way.** Today's IDR 17,229,139.20 safe amount is less than the trip price, but exceeds the first installment. The user accepts partial_payment and installments, not full_payment; the request prohibits partial payment. That leaves an eligible installment schedule, even though the capacity-only full-payment date is 15 September.

message_01 raises monthly pay from the historical IDR 33,345,000 to IDR 42,750,000 effective 15 August. This supports larger future payments, but is not cash available on 5 August. event_185 reserves IDR 1,651,100 on 8 August, the same day the plan starts. The selected three-payment option finishes 7 October before the 10 October deadline. The 18-payment alternative exceeds the seven-month preference and the deadline. The sample asserts the complete installment trajectory is safe; comparing only its first payment with today's safe amount is not enough to verify that.

**Schedule checked.** Matches `payment_option_05` exactly: 3 payments every 30 days, total IDR 47,858,720.01, including IDR 1,840,720.01 financing fees. Last payment 2025-10-07 is on or before the deadline. Use the supplied rounded payment amounts; do not adjust the last installment to remove the stated fee.

## request_03

**Net salary, one-off arrears, wait.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_03 |
| user_id | user_03 |
| request_date | 2019-09-03 |
| request_type | education |
| requested_amount | 5491000 |
| desired_completion_date | 2019-11-15 |
| allows_partial_payment | false |
| request_text | Should I pay for the course now, use installments, or wait? I need to decide by 15 November 2019. The course I want to take is IDR 5,491,000. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 873000 |
| affordability_status | affordable_later |
| recommended_payment_method | wait |
| payment_plan | 2019-11-15:5491000 |
| earliest_date_for_full_payment | 2019-11-15 |
| spending_changes_needed | none |
| decision_explanation | Pay IDR 5,491,000 in full on 15 November 2019. Paying earlier would take the balance below the IDR 2,668,700 minimum. |

**Financial context.** Current balance: IDR 5,810,300; minimum to keep: IDR 2,668,700. Accepted methods: full_payment, partial_payment, installments. Installment limit: 2. Protected categories: rent, utilities, groceries.

**Why I read the answer this way.** Only IDR 873,000 is safe today against a course price of IDR 5,491,000. Although the profile accepts partial payments, this request does not. The supplied installment offers require 21 or 24 payments, far beyond the two-month limit and the course deadline. Waiting for an eligible full payment is therefore the sample's choice.

message_02 confirms regular payroll and distinguishes it from a one-off adjustment. Historical regular payroll is IDR 4,365,000; event_211 is separate promotion arrears of IDR 1,964,250 and should not recur. image_01 supplies IDR 4,365,000 net salary for blank-amount event_253, rather than gross earnings IDR 4,780,800. event_254 is a pending IDR 95,000 pharmacy debit. The sample locates the first safe full payment on 15 November, exactly the deadline, after further payroll cycles.

Reconstruction caveat: August has a regular payroll row and an additional net-salary image row. Their presence does not authorize repeating two monthly salaries or adding settled salary again to current cash. The exact November threshold needs the daily forecast, not merely the payslip amount.

**Payment arithmetic checked.** The dated payment(s) total IDR 5,491,000, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_04

**Partial allowed by request but rejected by user.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_04 |
| user_id | user_04 |
| request_date | 2024-06-04 |
| request_type | family_transfer |
| requested_amount | 12693000 |
| desired_completion_date | 2024-06-19 |
| allows_partial_payment | true |
| request_text | The amount I want to send is IDR 12,693,000. Would sending the money now leave enough for my upcoming expenses? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 8401800 |
| affordability_status | affordable_later |
| recommended_payment_method | wait |
| payment_plan | 2024-06-15:12693000 |
| earliest_date_for_full_payment | 2024-06-15 |
| spending_changes_needed | none |
| decision_explanation | Wait until 15 June 2024, then pay IDR 12,693,000 in full. Paying sooner would put the IDR 30,686,600 minimum at risk. |

**Financial context.** Current balance: IDR 52,206,950; minimum to keep: IDR 30,686,600. Accepted methods: full_payment. Installment limit: blank (no installment consent). Protected categories: rent, groceries, transport.

**Why I read the answer this way.** The request permits part payment, but the user accepts only full_payment. The IDR 8,401,800 safe today therefore cannot be used as an eligible partial-payment recommendation. The sample waits until 15 June, before the 19 June deadline, when the full transfer is reported safe.

Regular historical payroll is IDR 38,190,000 on the 15th. message_03 says the quarterly bonus has no approved final amount or payment date, so a past bonus must not be projected as guaranteed income. event_357 is an IDR 1,704,300 school fee settling 11 June that must remain reserved. These obligations explain why current cash less the reserve is not all spendable. The installment offer is excluded by the user's preference.

**Payment arithmetic checked.** The dated payment(s) total IDR 12,693,000, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_05

**Final payroll and unusable long plans.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_05 |
| user_id | user_05 |
| request_date | 2025-11-06 |
| request_type | debt_repayment |
| requested_amount | 15488 |
| desired_completion_date | 2026-01-12 |
| allows_partial_payment | false |
| request_text | Can I clear this additional amount without putting upcoming bills at risk? The extra repayment I'm considering is ZAR 15,488. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 737 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not make this payment by 12 January 2026. None of the available options keeps the ZAR 13,100 minimum protected. |

**Financial context.** Current balance: ZAR 46,475.10; minimum to keep: ZAR 13,100. Accepted methods: full_payment, partial_payment, installments. Installment limit: 4. Protected categories: rent, healthcare, family_support, groceries.

**Why I read the answer this way.** ZAR 737 is positive capacity for a smaller payment, not permission to commit ZAR 15,488. Partial payments are prohibited by this request. The only installment offers have 18 and 24 payments, exceeding the four-month limit and January deadline.

The most recent payroll is explicitly Final employer payroll, event_390 on 15 October, ZAR 14,740. There is no next confirmed salary; continuing that salary indefinitely would be an unsupported assumption. Protected rent, healthcare, family support, and groceries consume the cash reserve over time. event_438 is a failed utility debit, not a settled payment; failure also does not establish that future recurring utilities disappear. The blank full-payment date records the sample's conclusion that the full amount is not safe within the forecast. No eligible complete plan is supplied.

## request_06

**Small cut enables payment before deadline.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_06 |
| user_id | user_06 |
| request_date | 2026-01-03 |
| request_type | investment |
| requested_amount | 620.4 |
| desired_completion_date | 2026-01-14 |
| allows_partial_payment | false |
| request_text | I want to put EUR 620.40 into an investment. I need to complete it by 14 January 2026. Is it safer to invest now, invest a smaller amount, or wait? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 603.3 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | full_payment |
| payment_plan | 2026-01-03:620.40 |
| earliest_date_for_full_payment | 2026-01-15 |
| spending_changes_needed | stop:event_476 |
| decision_explanation | Stop the family streaming plan, then pay EUR 620.40 today. This leaves at least EUR 800 available. |

**Financial context.** Current balance: EUR 1,942.40; minimum to keep: EUR 800. Accepted methods: full_payment, partial_payment. Installment limit: blank (no installment consent). Protected categories: rent, insurance, transport.

**Why I read the answer this way.** The investment exceeds the unmodified safe amount by just EUR 17.10: 620.40 - 603.30. event_476 identifies a EUR 19 recurring family streaming plan, marked stoppable, and the profile explicitly permits stopping streaming. Removing a future EUR 19 occurrence can cover that shortfall if it occurs before the limiting balance date; the sample says this change makes today's full payment safe.

This is affordable_with_plan, despite using full_payment, because a spending change is required. amount_safe_to_pay stays EUR 603.30 because that field is measured before optional changes. The unchanged-budget full-payment date remains 15 January, one day after the request deadline; the adjusted plan instead pays on 3 January. message_04 specifies temporary pay of EUR 1,037.52, so historical higher pay must not be used. event_557 is cancelled and adds no debit. Stopping event_476 means stopping future recurrence, not refunding the settled December charge.

**Payment arithmetic checked.** The dated payment(s) total EUR 620.40, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_07

**Installments only; salary delay.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_07 |
| user_id | user_07 |
| request_date | 2024-09-05 |
| request_type | housing |
| requested_amount | 197400 |
| desired_completion_date | 2024-11-14 |
| allows_partial_payment | true |
| request_text | How much of the rental deposit can I safely pay today? I need to decide by 14 November 2024. The rental deposit is INR 197,400. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 87170.56 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | installments |
| payment_plan | 2024-09-12:68432&#124;2024-10-10:68432&#124;2024-11-07:68432 |
| earliest_date_for_full_payment | 2024-10-23 |
| spending_changes_needed | none |
| decision_explanation | Use 3 installments of INR 68,432, starting 12 September 2024. This leaves at least INR 93,000 available. |

**Financial context.** Current balance: INR 218,945.56; minimum to keep: INR 93,000. Accepted methods: installments. Installment limit: 12. Protected categories: rent, utilities, debt_repayment.

**Why I read the answer this way.** The user accepts installments only. Today's INR 87,170.56 safe capacity is below the deposit price but greater than the first INR 68,432 installment. The selected three-payment option finishes 7 November, before the 14 November deadline, and is within the twelve-month preference. The 15-payment offer is too long.

message_05 explicitly postpones the confirmed September salary to 23 September; do not count it on 15 September. The sample schedules the first installment on 12 September using existing cash, then later payments around subsequent income. Its full-payment date of 23 October is capacity information, not a recommendation to use a method the user rejects.

Reconstruction caveat: message_05 explicitly gives 23 September. Treating the 23rd as a continuing payday in later months requires a recurrence assumption; the exact 23 October threshold is supplied by the sample and is not independently established by that one message.

**Schedule checked.** Matches `payment_option_19` exactly: 3 payments every 28 days, total INR 205,296, including INR 7,896 financing fees. Last payment 2024-11-07 is on or before the deadline. Use the supplied rounded payment amounts; do not adjust the last installment to remove the stated fee.

## request_08

**Reduced-pay wording and waiting.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_08 |
| user_id | user_08 |
| request_date | 2025-02-07 |
| request_type | emergency_expense |
| requested_amount | 996.6 |
| desired_completion_date | 2025-04-15 |
| allows_partial_payment | false |
| request_text | The repair I need is priced at EUR 996.60. Can I cover the full repair now and still manage my essential expenses? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 284.57 |
| affordability_status | affordable_later |
| recommended_payment_method | wait |
| payment_plan | 2025-04-15:996.60 |
| earliest_date_for_full_payment | 2025-04-15 |
| spending_changes_needed | none |
| decision_explanation | Pay EUR 996.60 in full on 15 April 2025. Paying earlier would take the balance below the EUR 800 minimum. |

**Financial context.** Current balance: EUR 1,536.57; minimum to keep: EUR 800. Accepted methods: full_payment. Installment limit: blank (no installment consent). Protected categories: rent, education, groceries, debt_repayment.

**Why I read the answer this way.** Only full_payment is accepted, and the request prohibits partial payment. EUR 284.57 safe today cannot cover the EUR 996.60 repair. The sample places the first safe full payment on 15 April, exactly the deadline. The long installment offer is not eligible.

message_06 states the next salary is EUR 1,422.85 following unpaid-leave adjustment. The ledger shows EUR 1,422.85 in earlier months and EUR 782.57 on 15 January. This makes the wording reduced ambiguous relative to the latest ledger amount: use the explicit upcoming amount, not a second invented percentage reduction. The sample's April date reflects its cash-flow projection with protected commitments, rather than implying that the very next payday is necessarily sufficient.

**Payment arithmetic checked.** The dated payment(s) total EUR 996.60, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_09

**Small purchase; safe amount is capped.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_09 |
| user_id | user_09 |
| request_date | 2026-07-04 |
| request_type | other |
| requested_amount | 166.61 |
| desired_completion_date | 2026-07-23 |
| allows_partial_payment | true |
| request_text | Is the full membership fee affordable today, or should I wait? The annual membership costs EUR 166.61. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 166.61 |
| affordability_status | affordable_now |
| recommended_payment_method | full_payment |
| payment_plan | 2026-07-04:166.61 |
| earliest_date_for_full_payment | 2026-07-04 |
| spending_changes_needed | none |
| decision_explanation | Pay EUR 166.61 today. This keeps the EUR 600 minimum available over the next 90 days. |

**Financial context.** Current balance: EUR 2,231.10; minimum to keep: EUR 600. Accepted methods: full_payment, partial_payment, installments. Installment limit: 2. Protected categories: rent, utilities, groceries.

**Why I read the answer this way.** The membership costs only EUR 166.61, and the sample reports that entire amount as safe. Full payment is accepted and requires no spending changes. After paying, current cash is EUR 2,064.49, compared with a EUR 600 minimum; the sample also asserts the 90-day floor stays protected.

The historical income records are variable client/project payments, not a single fixed salary. Do not create new unconfirmed invoices merely to justify the result. Both installment offers are far longer than the two-month preference and add fees. Immediate full payment is the straightforward eligible plan. A safe amount equal to the request means the output has hit its cap, not that this is the user's absolute maximum spending capacity.

**Payment arithmetic checked.** The dated payment(s) total EUR 166.61, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_10

**Pending platform income is not cash.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_10 |
| user_id | user_10 |
| request_date | 2024-12-06 |
| request_type | purchase |
| requested_amount | 266700 |
| desired_completion_date | 2025-02-10 |
| allows_partial_payment | true |
| request_text | The price of the laptop is INR 266,700. I need to complete it by 10 February 2025. How much of the laptop price can I safely cover today? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 12700 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not make this payment by 10 February 2025. None of the available options keeps the INR 225,400 minimum protected. |

**Financial context.** Current balance: INR 750,155; minimum to keep: INR 225,400. Accepted methods: partial_payment, installments. Installment limit: 6. Protected categories: rent, groceries, transport.

**Why I read the answer this way.** The INR 750,155 current balance looks large, but only INR 12,700 is reported safe after the forecast and INR 225,400 minimum. message_07 says the next platform payout remains pending and unwithdrawable. Historical weekly earnings do not make that pending balance spendable, and unsupported future payouts must not be invented.

The user accepts partial payments and installments. Partial payment is permitted by the request, but it needs a safe second payment that completes all INR 266,700 by 10 February; the sample supplies no full-payment date. The 15-payment installment offer exceeds the six-month limit and deadline. Thus a small safe amount today cannot justify an incomplete laptop purchase. The sample's exact INR 12,700 reflects its conservative forecast, not current balance minus minimum alone.

## request_11

**Recurring dining reduction enables payment.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_11 |
| user_id | user_11 |
| request_date | 2025-05-03 |
| request_type | travel |
| requested_amount | 13110000 |
| desired_completion_date | 2025-06-12 |
| allows_partial_payment | false |
| request_text | Does paying for the trip now leave enough for the rest of the month? I need to decide by 12 June 2025. I'm planning a family trip that costs IDR 13,110,000. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 12510645 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | full_payment |
| payment_plan | 2025-05-03:13110000 |
| earliest_date_for_full_payment | 2025-07-15 |
| spending_changes_needed | reduce_to:event_989:665950 |
| decision_explanation | Reduce the weekend food delivery to IDR 665,950, then pay IDR 13,110,000 today. This leaves at least IDR 34,140,600 available. |

**Financial context.** Current balance: IDR 63,531,795; minimum to keep: IDR 34,140,600. Accepted methods: full_payment. Installment limit: blank (no installment consent). Protected categories: housing, utilities, education.

**Why I read the answer this way.** The unmodified shortfall is IDR 599,355: 13,110,000 - 12,510,645. The user accepts only full_payment. Without changes the sample's full-payment date is 15 July, after the 12 June travel deadline, so waiting would miss completion.

The selected change refers to event_989, a reducible dining expense named Weekend food delivery. Its recorded amount is IDR 1,163,530.49 and its minimum_allowed_amount is IDR 665,950, exactly the proposed target. Dining is permitted for reductions and is not protected. The per-occurrence reduction is IDR 497,580.49, which is less than the full shortfall: this explanation relies on future recurring savings over the relevant trajectory, not a refund or a single reduction of the historical transaction.

message_08 explicitly confirms base salary IDR 38,760,000 and says commissions remain unapproved. The historical base rows are IDR 23,256,000; the newer explicit amount is an amendment, while historical commissions are not guaranteed future income. The sample says the permitted reduction enables full payment today, hence affordable_with_plan; the safe-today amount and July full-payment date remain the unchanged-budget measurements.

**Payment arithmetic checked.** The dated payment(s) total IDR 13,110,000, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_12

**Can afford full amount but rejects full payment.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_12 |
| user_id | user_12 |
| request_date | 2026-04-05 |
| request_type | education |
| requested_amount | 65164 |
| desired_completion_date | 2026-06-20 |
| allows_partial_payment | false |
| request_text | The professional course costs ZAR 65,164. Can I pay for the course before enrolment closes? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 65164 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | installments |
| payment_plan | 2026-04-19:22590.19&#124;2026-05-20:22590.19&#124;2026-06-20:22590.19 |
| earliest_date_for_full_payment | 2026-04-05 |
| spending_changes_needed | none |
| decision_explanation | Use 3 installments of ZAR 22,590.19, starting 19 April 2026. This leaves at least ZAR 43,200 available. |

**Financial context.** Current balance: ZAR 193,089.89; minimum to keep: ZAR 43,200. Accepted methods: partial_payment, installments. Installment limit: 11. Protected categories: rent, utilities, groceries.

**Why I read the answer this way.** This is the clearest example of financial capacity differing from payment preference. The full ZAR 65,164 is safe today, and earliest_date_for_full_payment is the request date, but the user does not accept full_payment. They accept partial payments and installments; this request prohibits partial payment.

The selected three-installment offer is therefore the eligible route, finishing exactly on 20 June. The 21-payment alternative exceeds the eleven-month limit and deadline. message_09 says the seasonal contract has ended with no confirmed renewal. The substantial current cash must fund the projection without invented off-season wages. The sample classifies the chosen installment method as affordable_with_plan even though a hypothetical lump sum would be financially possible.

**Schedule checked.** Matches `payment_option_33` exactly: 3 payments every 31 days, total ZAR 67,770.57, including ZAR 2,606.57 financing fees. Last payment 2026-06-20 is on or before the deadline. Use the supplied rounded payment amounts; do not adjust the last installment to remove the stated fee.

## request_13

**Do not assume second household income continues.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_13 |
| user_id | user_13 |
| request_date | 2024-03-07 |
| request_type | family_transfer |
| requested_amount | 941.6 |
| desired_completion_date | 2024-05-15 |
| allows_partial_payment | true |
| request_text | Can I complete this family transfer and still keep my minimum balance? I want to send EUR 941.60 to my family. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 433.4 |
| affordability_status | affordable_later |
| recommended_payment_method | wait |
| payment_plan | 2024-05-15:941.60 |
| earliest_date_for_full_payment | 2024-05-15 |
| spending_changes_needed | none |
| decision_explanation | Pay EUR 941.60 in full on 15 May 2024. Paying earlier would take the balance below the EUR 1,300 minimum. |

**Financial context.** Current balance: EUR 2,789.52; minimum to keep: EUR 1,300. Accepted methods: full_payment. Installment limit: blank (no installment consent). Protected categories: rent, groceries, transport.

**Why I read the answer this way.** The user accepts full_payment only, despite the request allowing partial payment. EUR 433.40 safe today therefore cannot be offered as a first part-payment. The sample waits until 15 May, exactly the deadline, for the full EUR 941.60.

event_1161 confirms EUR 1,343.54 for 15 March, matching primary household salary. A second household income appears through January but has no February row or next confirmed payment. Its continuation should not be assumed solely to make the transfer safe. There is no message explicitly declaring termination, so the absence supports caution rather than proving employment ended. Long installment offers are excluded by preference. The precise May date requires the conservative expense and income projection.

**Payment arithmetic checked.** The dated payment(s) total EUR 941.60, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_14

**Partial payment needs safe completion.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_14 |
| user_id | user_14 |
| request_date | 2025-08-04 |
| request_type | debt_repayment |
| requested_amount | 5414.2 |
| desired_completion_date | 2025-10-04 |
| allows_partial_payment | true |
| request_text | I'm planning an extra loan payment of EUR 5,414.20. I need to complete it by 4 October 2025. Would paying this much toward the loan leave enough for the rest of the month? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 597.74 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not proceed with the EUR 5,414.20 request. Although EUR 597.74 is available today, the full amount cannot be completed safely within 90 days. |

**Financial context.** Current balance: EUR 3,931.74; minimum to keep: EUR 2,200. Accepted methods: partial_payment. Installment limit: blank (no installment consent). Protected categories: rent, healthcare, family_support, groceries.

**Why I read the answer this way.** The user accepts only partial_payment. The request permits it, and EUR 597.74 is safe today, but the remaining EUR 4,816.46 must also be safely payable by 4 October under the two-payment rule. The sample's blank full-payment date means it finds no such capacity in the forecast, so it recommends no payment instead of an incomplete transfer to the loan.

message_10 confirms EUR 2,717 salary resuming on 15 August and a new recurring childcare payment. Resumed income cannot be treated as entirely discretionary; the new dependent-care commitment and other protected expenses matter. Full payment and installments are not accepted methods. The sample's not_affordable also asserts financial insufficiency, beyond those preference exclusions; reproducing that numerical assertion needs the 90-day ledger.

## request_15

**Only accepted method prohibited by request.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_15 |
| user_id | user_15 |
| request_date | 2026-01-06 |
| request_type | investment |
| requested_amount | 3685 |
| desired_completion_date | 2026-02-01 |
| allows_partial_payment | false |
| request_text | How much can I invest now without affecting essential payments? I need to decide by 1 February 2026. I have an opportunity to invest EUR 3,685. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 83.05 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not make this payment by 1 February 2026. None of the available options keeps the EUR 1,200 minimum protected. |

**Financial context.** Current balance: EUR 1,770.05; minimum to keep: EUR 1,200. Accepted methods: partial_payment. Installment limit: blank (no installment consent). Protected categories: rent, education, groceries, debt_repayment.

**Why I read the answer this way.** The only method this user accepts is partial_payment, but allows_partial_payment=false for this investment request. That leaves no eligible payment method even before checking amounts: full payment and the 21/24-payment installment offers are not accepted.

Financially, the sample also reports only EUR 83.05 safe today against EUR 3,685 requested and no safe full-payment date. message_11 confirms the first EUR 1,661 salary for 15 January, which is future income rather than cash available on 6 January. Education, rent, groceries, and debt repayments stay protected. The example illustrates both an eligibility failure and a forecast shortfall, not a blanket rule against investing.

## request_16

**Outstanding rent balance and rent increase.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_16 |
| user_id | user_16 |
| request_date | 2023-08-12 |
| request_type | housing |
| requested_amount | 122500 |
| desired_completion_date | 2023-10-11 |
| allows_partial_payment | true |
| request_text | The landlord has asked for a deposit of INR 122,500. Can I pay the rental deposit by the requested date? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 122500 |
| affordability_status | affordable_now |
| recommended_payment_method | full_payment |
| payment_plan | 2023-08-12:122500 |
| earliest_date_for_full_payment | 2023-08-12 |
| spending_changes_needed | none |
| decision_explanation | Pay INR 122,500 today. This leaves at least INR 122,400 available over the next 90 days. |

**Financial context.** Current balance: INR 362,370; minimum to keep: INR 122,400. Accepted methods: full_payment, installments. Installment limit: 2. Protected categories: rent, groceries, transport.

**Why I read the answer this way.** The sample says the complete INR 122,500 deposit is safe now. Full payment is accepted, and no spending cuts are allowed or needed. The installment alternatives have six or fifteen payments, exceeding the two-month limit.

image_02 is essential: the older rent receipt shows INR 200,000 total, INR 100,000 already received, and INR 100,000 still due. Blank-amount event_1442 is specifically the outstanding balance, scheduled for 16 August; reserve INR 100,000, not zero and not the entire INR 200,000. message_12 also increases future monthly rent by 12%. Historical salary is INR 173,000 on the 15th. After today's deposit cash is INR 239,870; paying the separate INR 100,000 liability would leave INR 139,870 before other movements, compared with INR 122,400 minimum. That arithmetic illustrates why the amount extraction matters, but the sample's full safety claim still requires all dated expenses and payroll.

**Payment arithmetic checked.** The dated payment(s) total INR 122,500, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_17

**Installments only; image-derived grocery expense.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_17 |
| user_id | user_17 |
| request_date | 2026-03-01 |
| request_type | emergency_expense |
| requested_amount | 274600 |
| desired_completion_date | 2026-05-04 |
| allows_partial_payment | false |
| request_text | What is the most I can put toward this repair right now? The latest estimate for the repair is INR 274,600. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 243849.58 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | installments |
| payment_plan | 2026-03-01:95194.67&#124;2026-03-31:95194.67&#124;2026-04-30:95194.67 |
| earliest_date_for_full_payment | 2026-03-15 |
| spending_changes_needed | none |
| decision_explanation | Use 3 installments of INR 95,194.67, starting 1 March 2026. This leaves at least INR 166,100 available. |

**Financial context.** Current balance: INR 550,379.58; minimum to keep: INR 166,100. Accepted methods: installments. Installment limit: 3. Protected categories: rent, education, groceries, debt_repayment.

**Why I read the answer this way.** The user accepts installments only, with a three-month limit. Today's INR 243,849.58 safe capacity is below the INR 274,600 repair price, yet comfortably exceeds the first INR 95,194.67 installment. The three-payment option starts immediately and finishes 30 April before the 4 May deadline. The 18-payment alternative is ineligible.

event_1546 confirms INR 206,000 salary on 15 March, also the sample's capacity-only full-payment date. That does not permit recommending a lump sum to a user who accepts only installments. image_03 supplies INR 41,272 for settled grocery event_1545 on 27 February. Use it as historical spending evidence, without subtracting the settled transaction again from current balance or confusing it with the requested repair amount.

**Schedule checked.** Matches `payment_option_47` exactly: 3 payments every 30 days, total INR 285,584.01, including INR 10,984.01 financing fees. Last payment 2026-04-30 is on or before the deadline. Use the supplied rounded payment amounts; do not adjust the last installment to remove the stated fee.

## request_18

**Own-account transfers are not income.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_18 |
| user_id | user_18 |
| request_date | 2026-07-07 |
| request_type | other |
| requested_amount | 3246.1 |
| desired_completion_date | 2026-09-15 |
| allows_partial_payment | false |
| request_text | The annual plan comes to EUR 3,246.10. I need to complete it by 15 September 2026. Can I take the membership and still keep my minimum balance intact? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 462 |
| affordability_status | affordable_later |
| recommended_payment_method | wait |
| payment_plan | 2026-09-15:3246.10 |
| earliest_date_for_full_payment | 2026-09-15 |
| spending_changes_needed | none |
| decision_explanation | Pay EUR 3,246.10 in full on 15 September 2026. Paying earlier would take the balance below the EUR 1,400 minimum. |

**Financial context.** Current balance: EUR 2,486; minimum to keep: EUR 1,400. Accepted methods: full_payment, partial_payment. Installment limit: blank (no installment consent). Protected categories: housing, healthcare, utilities.

**Why I read the answer this way.** EUR 462 is safe today, below the EUR 3,246.10 membership. The profile accepts full and partial payments, but this request prohibits partial payment and the profile does not accept installments. The sample therefore chooses a single full payment on 15 September, exactly the deadline.

message_13 identifies matching debit and credit entries as a transfer between the user's own accounts. That is not new salary and cannot support a second income stream. Historical payroll is EUR 2,310 on the 15th; multiple cycles of income minus commitments underlie the reported September capacity. The current balance is itself below the membership price, and preserving EUR 1,400 makes an immediate payment still less plausible.

**Payment arithmetic checked.** The dated payment(s) total EUR 3,246.10, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_19

**Two-payment plan avoids installment fees.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_19 |
| user_id | user_19 |
| request_date | 2024-09-04 |
| request_type | purchase |
| requested_amount | 39660 |
| desired_completion_date | 2024-10-04 |
| allows_partial_payment | true |
| request_text | Can I buy the laptop now without making next month's bills tight? I need to decide by 4 October 2024. I've been quoted INR 39,660 for the laptop. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 28820 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | partial_payment |
| payment_plan | 2024-09-04:28820&#124;2024-09-15:10840 |
| earliest_date_for_full_payment | 2024-09-15 |
| spending_changes_needed | none |
| decision_explanation | Pay INR 28,820 today and the remaining INR 10,840 on 15 September 2024. This completes the full request and keeps the INR 92,800 minimum protected. |

**Financial context.** Current balance: INR 199,545; minimum to keep: INR 92,800. Accepted methods: partial_payment, installments. Installment limit: 2. Protected categories: rent, healthcare, family_support, groceries.

**Why I read the answer this way.** This is the one supplied partial-payment example. Both the request and profile permit it. INR 28,820 is strictly between zero and INR 39,660, and the second payment is INR 10,840 = 39,660 - 28,820. It occurs on the reported full-payment date, 15 September, before the 4 October deadline. The two entries complete exactly the requested amount.

The two-installment seller option totals INR 41,246.40, including INR 1,586.40 in fees; the supplied partial-payment plan totals INR 39,660. If both are safe, the no-change lower-cost partial plan ranks ahead. A partial-payment schedule need not match a seller installment offer. The three-installment alternative is beyond the two-month preference and completes after the deadline.

Historical salary is INR 131,000 on the 15th. image_04 supports delivered grocery event_1700 and shows INR 2,854 as Item Bill, but the screenshot is cropped before a fully visible final bill section. That limits independent recovery of a final all-in grocery amount. Also, a future date safe for one full payment does not alone prove safety after an earlier part payment; the combined two-payment trajectory still needs checking.

**Payment arithmetic checked.** The dated payment(s) total INR 39,660, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_20

**Pending refund versus overdue telecom debit.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_20 |
| user_id | user_20 |
| request_date | 2026-02-07 |
| request_type | travel |
| requested_amount | 303700 |
| desired_completion_date | 2026-02-22 |
| allows_partial_payment | false |
| request_text | I can book the family trip for INR 303,700. Would it be safer to book the trip now or wait until more money comes in? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 5400 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not make this payment by 22 February 2026. None of the available options keeps the INR 64,500 minimum protected. |

**Financial context.** Current balance: INR 102,609.05; minimum to keep: INR 64,500. Accepted methods: full_payment, partial_payment, installments. Installment limit: 11. Protected categories: housing, utilities, education.

**Why I read the answer this way.** The sample reports only INR 5,400 safe against INR 303,700, and the 22 February deadline is close. Partial payment is prohibited. The only installment offer has eighteen payments, exceeding the eleven-month preference and deadline. No safe full-payment date is supplied.

message_14 and event_1785 describe an INR 8,640 refund that is still pending; its expected 14 February date is not evidence that it has settled. event_1787 is an INR 4,470 pending debit on 8 February. image_05 supplies the blank telecom liability event_1786: INR 704.05 before/on 6 February and INR 822.05 after that date. With the request on 7 February and settlement scheduled 9 February, the late amount is relevant. The old INR 3,543.54 bill is shown as paid and must not be reserved again. These are commitments and uncertain receipts, not new discretionary cash.

## request_21

**Two distinct spending changes meet deadline.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_21 |
| user_id | user_21 |
| request_date | 2026-04-03 |
| request_type | education |
| requested_amount | 1574.4 |
| desired_completion_date | 2026-04-14 |
| allows_partial_payment | false |
| request_text | Is it safe to cover the full course fee by the deadline? Enrolment for the course comes to USD 1,574.40. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 1543.35 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | full_payment |
| payment_plan | 2026-04-03:1574.40 |
| earliest_date_for_full_payment | 2026-04-15 |
| spending_changes_needed | stop:event_1815&#124;reduce_to:event_1816:23.50 |
| decision_explanation | Stop the online backup subscription and reduce the streaming subscription to USD 23.50, then pay USD 1,574.40 today. This leaves at least USD 1,800 available. |

**Financial context.** Current balance: USD 3,911.35; minimum to keep: USD 1,800. Accepted methods: full_payment. Installment limit: blank (no installment consent). Protected categories: rent, utilities, groceries.

**Why I read the answer this way.** The request exceeds baseline safe capacity by USD 31.05: 1,574.40 - 1,543.35. The sample closes this gap by stopping event_1815 (USD 11 online backup subscription) and reducing event_1816 from USD 47 to its USD 23.50 minimum. Together those changes save USD 34.50 per corresponding cycle, enough to cover the shortfall when timed as in the sample.

Both referenced categories are permitted for these changes and are outside the protected rent/utilities/groceries categories. The events are distinct, satisfying the ban on stopping and reducing the same event. They reference past settled occurrences to identify future recurring subscriptions, not retroactive refunds. The next historical recurrence dates are around 9 April for streaming and 12 April for backup, before the confirmed 15 April salary event_1858.

The no-change full-payment date is 15 April, after the 14 April education deadline. With changes the sample pays on 3 April, hence affordable_with_plan with full_payment, while amount_safe_to_pay remains the baseline figure. Reserve event_1857 (USD 53 pending fuel authorization), and do not treat the USD 270.72 unrealized portfolio value event_1856 as cash.

**Payment arithmetic checked.** The dated payment(s) total USD 1,574.40, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_22

**Unrealized portfolio value is not cash.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_22 |
| user_id | user_22 |
| request_date | 2024-12-05 |
| request_type | family_transfer |
| requested_amount | 731.5 |
| desired_completion_date | 2025-02-10 |
| allows_partial_payment | true |
| request_text | The transfer I have in mind is EUR 731.50. I need to complete it by 10 February 2025. Can I make the full transfer without falling short on my own bills? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 475.46 |
| affordability_status | affordable_with_plan |
| recommended_payment_method | installments |
| payment_plan | 2024-12-08:253.59&#124;2025-01-05:253.59&#124;2025-02-02:253.59 |
| earliest_date_for_full_payment | 2025-01-15 |
| spending_changes_needed | none |
| decision_explanation | Use 3 installments of EUR 253.59, starting 8 December 2024. This leaves at least EUR 500 available. |

**Financial context.** Current balance: EUR 1,132.46; minimum to keep: EUR 500. Accepted methods: installments. Installment limit: 6. Protected categories: rent, groceries, transport.

**Why I read the answer this way.** Only installments are accepted. The request's permission for partial payment does not override that preference. EUR 475.46 is safe today, below the full EUR 731.50 but above the first EUR 253.59 installment. The selected three-payment plan completes 2 February, before 10 February, within the six-month limit. The 15-payment offer is too long.

message_15 explicitly says the increased portfolio value has not produced cash. event_1960 is EUR 369.60 unrealized value linked to investment purchase event_1959; it is not additional spending capacity. event_1961 reserves a EUR 43 merchant debit on the first installment date. Historical payroll is EUR 616 monthly. The 15 January full-payment date describes capacity only and does not make full payment an accepted recommendation.

**Schedule checked.** Matches `payment_option_61` exactly: 3 payments every 28 days, total EUR 760.77, including EUR 29.27 financing fees. Last payment 2025-02-02 is on or before the deadline. Use the supplied rounded payment amounts; do not adjust the last installment to remove the stated fee.

## request_23

**Uncredited prize cannot fund repayment.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_23 |
| user_id | user_23 |
| request_date | 2025-05-07 |
| request_type | debt_repayment |
| requested_amount | 38016 |
| desired_completion_date | 2025-07-15 |
| allows_partial_payment | false |
| request_text | How much extra can I put toward the loan today? I need to decide by 15 July 2025. The additional loan payment would be ZAR 38,016. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 9152 |
| affordability_status | affordable_later |
| recommended_payment_method | wait |
| payment_plan | 2025-07-15:38016 |
| earliest_date_for_full_payment | 2025-07-15 |
| spending_changes_needed | none |
| decision_explanation | Pay ZAR 38,016 in full on 15 July 2025. Paying earlier would take the balance below the ZAR 27,000 minimum. |

**Financial context.** Current balance: ZAR 51,957.90; minimum to keep: ZAR 27,000. Accepted methods: full_payment, partial_payment, installments. Installment limit: 12. Protected categories: rent, healthcare, family_support, groceries.

**Why I read the answer this way.** The request prohibits partial payment. The user accepts installments in principle, but the 18- and 24-payment offers exceed the twelve-month limit and deadline. With only ZAR 9,152 safe today, the sample waits until 15 July, exactly the deadline, to pay ZAR 38,016 in full.

message_16 says the prize claim is verified but still uncredited. It cannot be counted as cash or as a promised funding date. There is no upfront release-fee demand in this message, so uncredited does not itself mean a demonstrated scam. Historical salary is ZAR 45,760 on the 15th, and event_2042 reserves ZAR 1,553.20 for a pending pharmacy charge. The investment purchase event_2041 is a historical outflow, not a source of recurring income. The sample's July date is its forecast result.

**Payment arithmetic checked.** The dated payment(s) total ZAR 38,016, exactly the request, and finish by the deadline. This checks schedule arithmetic, not the 90-day balance floor.

## request_24

**Settled prize is one-off and already in balance.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_24 |
| user_id | user_24 |
| request_date | 2026-01-04 |
| request_type | investment |
| requested_amount | 109600 |
| desired_completion_date | 2026-02-08 |
| allows_partial_payment | true |
| request_text | I'm considering setting aside INR 109,600 for an investment. Would investing this amount leave my upcoming bills covered? |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 13420 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not proceed with the INR 109,600 request. Although INR 13,420 is available today, the full amount cannot be completed safely within 90 days. |

**Financial context.** Current balance: INR 85,045; minimum to keep: INR 51,000. Accepted methods: partial_payment. Installment limit: blank (no installment consent). Protected categories: rent, insurance, transport.

**Why I read the answer this way.** The user accepts partial_payment only and the request permits it, but a valid plan needs both the INR 13,420 first payment and the INR 96,180 remainder safely completed by 8 February. The sample supplies no safe full-payment date in the forecast, so it rejects the complete request rather than recommending an unsupported first payment.

Unlike request_23, message_17 confirms that prize proceeds have actually settled: event_2165 credits INR 33,550 on 28 December. This is historical cash already represented in the starting balance, not another future credit and not recurring prize income. event_2166 reserves INR 1,830 for scheduled insurance. Regular historical payroll is INR 61,000. Full-payment and installment offers cannot override the user's partial-only preference.

## request_25

**Dated FX conversion and no eligible long plan.**

Request fields:

| Field | Supplied value |
| --- | --- |
| request_id | request_25 |
| user_id | user_25 |
| request_date | 2024-03-06 |
| request_type | housing |
| requested_amount | 60496000 |
| desired_completion_date | 2024-04-17 |
| allows_partial_payment | true |
| request_text | Is the deposit affordable now, or do I need more time? I need IDR 60,496,000 for the rental deposit. |

Answer fields (request_id is shared with the request above):

| Field | Supplied value |
| --- | --- |
| amount_safe_to_pay | 1425000 |
| affordability_status | not_affordable |
| recommended_payment_method | not_recommended |
| payment_plan | none |
| earliest_date_for_full_payment | empty |
| spending_changes_needed | none |
| decision_explanation | Do not make this payment by 17 April 2024. None of the available options keeps the IDR 23,379,100 minimum protected. |

**Financial context.** Current balance: IDR 32,063,050; minimum to keep: IDR 23,379,100. Accepted methods: full_payment, installments. Installment limit: 3. Protected categories: rent, insurance, transport.

**Why I read the answer this way.** The IDR 60,496,000 housing deposit is large relative to the IDR 32,063,050 current balance and IDR 23,379,100 minimum. The sample reports only IDR 1,425,000 safe now and no safe full-payment date. Partial payment is permitted by the request but is not accepted by the user; the 15- and 24-payment offers exceed the three-month limit and 17 April deadline. The profile allows no spending cuts.

Income is denominated in USD while the output is IDR. event_2288 confirms USD 1,800 on 15 March. The supplied USD-to-IDR rate for that settlement date is 15,833.33, producing IDR 28,499,994 before any separately specified rounding. Do not invert the rate, substitute a live rate, or add already-settled historical salary again. event_2287 is a failed debit, not cash spent; it also does not mean recurring essential bills are cancelled. The sample concludes even the supported projected income does not make the whole deposit safely payable in the forecast.

## What is checked, and what remains a forecast assumption

All 25 examples have been covered. Every non-none plan is chronological, completes by its stated deadline, and has the expected total. All five selected installment schedules match an actual supplied option including dates, payment amounts, total payable, and fees. The one partial-payment plan sums to its request and uses the stated safe amount and full-payment date. All four individual spending-change actions across requests 06, 11, and 21 reference the correct user's permitted, non-protected flexible events and respect reduction minima.

The exact safe-today amounts, the claim that each reported full-payment date is the *first* safe date, and the assertion that every selected plan maintains its minimum balance have **not** been independently recomputed here. Those require a deterministic day-by-day reconstruction, including recurrence choices and variable-spending forecasts. In particular, request_07's later 23rd payday, request_08's reduced-pay wording, request_11's recurring savings, and request_19's cropped receipt deserve explicit handling when building that forecast. These notes explain the supplied answers and their evidential basis without treating sample labels as proof that an implementation is correct.
