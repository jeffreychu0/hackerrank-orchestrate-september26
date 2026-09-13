# Cross-model evaluation

Each request's evidence was read independently by both providers, then both readings were shown - unlabelled and in a per-request randomised order - to each provider for adjudication. Every item is therefore judged once by a model that produced one of the readings and once by one that produced the other.

## Models

| Role | Provider | Model |
|---|---|---|
| producer and judge | openai | `gpt-5.4` |
| producer and judge | anthropic | `claude-sonnet-5` |

## Eval set

| Property | Count |
|---|---:|
| items | 19 |
| claims differ | 15 |
| output row differs | 1 |
| claims differ without output change | 14 |

## Preference by judge

| Judge | Items | Prefers openai | Prefers anthropic | Equivalent | Neither |
|---|---:|---:|---:|---:|---:|
| openai | 19 | 4 | 5 | 9 | 1 |
| anthropic | 19 | 2 | 7 | 10 | 0 |

## Self-preference bias

A judge that rates its own reading higher than the other judge rates that same reading is showing self-preference. The gap is the estimate; it is not assumed to be zero.

| Reading produced by | Preferred by itself | Preferred by the other judge | Gap |
|---|---:|---:|---:|
| openai | 44% | 22% | +22% |
| anthropic | 78% | 56% | +22% |

## Judge agreement

| Property | Value |
|---|---:|
| items judged by both | 19 |
| identical verdict | 11 |
| identical verdict rate | 0.5789 |
| items where both picked a side | 6 |
| agreed when both picked a side | 4 |

## Judge calibration against the published answers

Requests that have a sample answer and where exactly one producer got the field right. Anything near 50% means the verdicts carry no information.

| Field | Discriminating items | Judge correct | Rate |
|---|---:|---:|---:|
| amount_safe_to_pay | 0 | 0 | n/a |
| affordability_status | 0 | 0 | n/a |
| recommended_payment_method | 0 | 0 | n/a |

## Most common criticisms

**openai**

- (1x) Overstates certainty by marking no_material_effect as confirmed even though the one-time adjustment is mention
- (1x) Uses no_material_effect despite evidence of a one-time adjustment next payroll; while no ongoing pattern chang
- (1x) Marks certainty as 'confirmed' even though the underlying message is about an unapproved bonus; while the lack
- (1x) Uses scope 'single_event', which is not especially well aligned to the fact that no specific event change is b
- (1x) Uses an inferred effective_date (2025-02-14) that is not explicitly stated in the evidence.
- (1x) Uses certainty 'confirmed' despite unresolved mapping between QuickCrew and the detected platform_earnings pat
- (1x) Uses scope 'ongoing' even though the message supports, at most, excluding the next unsettled payout, not the w
- (1x) Applies exclude_projection to event_839 / the detected pattern without establishing that QuickCrew is the whol

**anthropic**

- (1x) Uses no_material_effect despite evidence of a one-time adjustment next payroll; while no ongoing pattern chang
- (1x) Uses event_ids ['event_284'] even though the message is not about that specific salary event and no pattern-sp
- (1x) Sets scope to 'ongoing' although the evidence does not describe an ongoing change to salary or any recurring s
- (1x) Adds extra inference about bonuses not being part of any detected recurring pattern; plausible, but unnecessar
- (1x) Invents an effective_date of 2026-01-14, which is not supported by the employer message or recurring pattern d
- (1x) Uses an inferred effective_date (2025-02-14) that is not explicitly stated in the evidence.
- (1x) Says unpaid leave was 'already taken,' which is not stated by the message.
- (1x) Includes speculation in unresolved_questions about whether the amount reverts to the prior pattern.

## Facts both readings missed

Flagged by a judge on both readings at once, so no amount of provider choice would fix them. These are the candidates for a prompt or vocabulary change.

- (1x) Neither reading explicitly acknowledges that the next payroll amount may differ for a single occurrence becaus
- (1x) Neither reading avoids supplying an effective_date despite the evidence not stating the actual next pay date.
- (1x) The evidence is specifically about the next payout being pending and variable; if any claim is made, it should
- (1x) Because the host's detected salary pattern appears to combine multiple platform sources, the safest faithful r
- (1x) Neither reading explicitly notes the ambiguity that the message may only justify excluding unsettled commissio
- (1x) A new recurring childcare-related expense/deduction begins in August / from the next payroll cycle.
- (1x) The amount of that new recurring expense is not established and should be left unspecified rather than omitted
- (1x) Neither reading notes that the message supports the amount mathematically only because the host detected curre
- (1x) Neither reading flags any residual uncertainty around whether 'has changed' should be treated as fully confirm
- (1x) Neither reading creates any forward-looking flag or exclude_projection/event note for the upcoming payslip's o

## Adjudication cost

| Judge | Calls | Tokens | Est. cost |
|---|---:|---:|---:|
| openai | 19 | 45,396 | $0.0993 |
| anthropic | 19 | 91,686 | $0.4093 |
