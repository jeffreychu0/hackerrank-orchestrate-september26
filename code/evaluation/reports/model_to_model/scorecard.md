# Cross-model evaluation

Each request's evidence was read independently by both providers, then both readings were shown - unlabelled and in a per-request randomised order - to each provider for adjudication. Every item is therefore judged once by a model that produced one of the readings and once by one that produced the other.

## Eval set

| Property | Count |
|---|---:|
| items | 19 |
| claims differ | 12 |
| output row differs | 1 |
| claims differ without output change | 11 |

## Preference by judge

| Judge | Items | Prefers openai | Prefers anthropic | Equivalent | Neither |
|---|---:|---:|---:|---:|---:|
| openai | 19 | 5 | 3 | 11 | 0 |
| anthropic | 19 | 5 | 4 | 10 | 0 |

## Self-preference bias

A judge that rates its own reading higher than the other judge rates that same reading is showing self-preference. The gap is the estimate; it is not assumed to be zero.

| Reading produced by | Preferred by itself | Preferred by the other judge | Gap |
|---|---:|---:|---:|
| openai | 62% | 56% | +7% |
| anthropic | 44% | 38% | +7% |

## Judge agreement

| Property | Value |
|---|---:|
| items judged by both | 19 |
| identical verdict | 15 |
| identical verdict rate | 0.7895 |
| items where both picked a side | 8 |
| agreed when both picked a side | 5 |

## Judge calibration against the published answers

Requests that have a sample answer and where exactly one producer got the field right. Anything near 50% means the verdicts carry no information.

| Field | Discriminating items | Judge correct | Rate |
|---|---:|---:|---:|
| amount_safe_to_pay | 0 | 0 | n/a |
| affordability_status | 0 | 0 | n/a |
| recommended_payment_method | 0 | 0 | n/a |

## Most common criticisms

**openai**

- (1x) Uses scope 'ongoing' for a message explicitly referring to the next payroll and a separate one-time adjustment
- (1x) Marks the no_material_effect claim as 'confirmed' even though the amount and exact effect of the one-time adju
- (1x) Uses certainty 'confirmed' for an interpretation that is better described as supported by the message but stil
- (1x) Uses scope 'single_event' on a no_material_effect claim, which is not especially well-matched to the evidence 
- (1x) Uses an exact effective_date (2025-02-14) that is not stated in the evidence and is only inferred from prior c
- (1x) Applies scope 'ongoing' even though the message speaks only about the next QuickCrew payout being pending.
- (1x) Targets event_839 / the weekly platform_earnings pattern without evidence that the whole detected stream is Qu
- (1x) Uses a broad no_material_effect claim even though the message introduces a new recurring childcare payment tha

**anthropic**

- (1x) Unnecessarily anchors the no_material_effect claim to salary category and event_284, even though the message i
- (1x) Uses scope 'ongoing' for a claim that is really just 'no confirmed change at this time'; this overstates the t
- (1x) Says the bonus is not part of any listed recurring pattern to exclude, which is fine, but the event_ids refere
- (1x) Invents an exact effective_date (2026-01-15) not stated in the evidence; it is inferred from the pattern rathe
- (1x) Uses an exact effective_date (2025-02-14) that is not stated in the evidence and is only inferred from prior c
- (1x) Adds period_days: 30, which is not necessary to the stated evidence claim and comes from host pattern inferenc
- (1x) Applies scope 'ongoing' even though the message speaks only about the next QuickCrew payout being pending.
- (1x) Targets event_839 / the weekly platform_earnings pattern without evidence that the whole detected stream is Qu

## Facts both readings missed

Flagged by a judge on both readings at once, so no amount of provider choice would fix them. These are the candidates for a prompt or vocabulary change.

- (1x) Neither reading leaves the date unspecified despite acknowledging in unresolved questions that the next payrol
- (1x) A narrower claim limited to the next occurrence, if any identifiable QuickCrew payout within the pattern could
- (1x) The message states a new recurring childcare payment begins in the same month and will appear from the next cy
- (1x) Neither reading notes that the message specifies the raise takes effect on the payroll cycle starting 2025-08-
- (1x) Neither reading captures that the one-time adjustment, once its amount is known, could itself warrant a future
- (1x) Neither reading explicitly notes that the bonus, once confirmed, would need to be evaluated separately as new_
- (1x) Neither reading questions whether 'confirmed' certainty is appropriate given the message's own hedging ('curre
- (1x) Neither reading notes that the shift from ~2024-09-22 (expected under 30d cadence) to 2024-09-23 is only a one
- (1x) Neither reading notes the apparent inconsistency that the message says the salary is 'reduced' to 1422.85, yet
- (1x) Both mark scope as 'ongoing' though the message describes the pending/closing status of a single upcoming payo

## Adjudication cost

| Judge | Calls | Tokens | Est. cost |
|---|---:|---:|---:|
| openai | 19 | 44,822 | $0.0942 |
| anthropic | 19 | 83,340 | $0.3268 |
