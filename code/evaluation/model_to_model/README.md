# Cross-model evaluation

The 25 published samples are the only labelled data in this challenge. They are
a good anchor and a small one: 25 rows, and the harness already agrees with 19
of them on all five judged fields, so further movement there is mostly noise.

This second eval trades ground truth for coverage. It works on any request in
the dataset by replacing "is this right" with "which of two independent readings
of the same evidence is better supported" — and it asks a model that did not
produce either reading.

## What is judged, and what is not

Only the interpretation step. Everything downstream of it is deterministic, so a
judge could not out-reason the engine, and any disagreement there would be a
complaint about arithmetic rather than about evidence. The judge never sees a
balance, a forecast or a recommendation.

## Design

```
request ──► provider A reads the evidence ──┐
        └─► provider B reads the evidence ──┤
                                            ├─► both readings, unlabelled,
                                            │   in randomised order
                                            ├─► judged by A
                                            └─► judged by B
```

Four properties keep it from being theatre:

- **Blind.** The judge sees "reading 1" and "reading 2", never a vendor name.
  The prompt is asserted by test to contain no provider or model name.
- **Order-randomised, reproducibly.** Position is a per-request hash, not a
  global RNG, so position cannot stand in for identity and the set rebuilds
  identically.
- **Bidirectional.** Every item is judged by both models, which turns
  self-preference from an assumption into a measurement: the gap between how
  often judge X prefers producer X and how often the *other* judge prefers that
  same reading.
- **Abstention allowed.** `equivalent` and `neither` are first-class verdicts,
  so the judge is never forced to invent a winner.

## Calibrating the judges

Cross-examination alone cannot tell you whether a judge is any good. On the
sample set the two providers produce the same output row 24 times in 25, so
there is almost never a case where exactly one was right — the ground-truth
calibration table comes back empty.

`--calibrate` runs the experiment that does work: each real reading is paired
against the same reading damaged in one known way, so the correct verdict is
known by construction.

| Defect | What it simulates |
|---|---|
| `scope_inflation` | a one-off adjustment silently becomes the new normal |
| `certainty_promotion` | hedged evidence recorded as settled fact, unlocking cash |
| `amount_drift` | a stated amount replaced by a nearby one |
| `scope_overreach` | a claim about one pattern widened to the whole category |
| `claim_omission` | a material fact missed |
| `claim_invention` | a commitment the evidence never mentions |

These are deliberately the failure modes deterministic validation *cannot*
catch. `harness/facts.py` already refuses an unknown source, an unowned event,
an invented category or an impossible date; nothing in code can tell that
`next_occurrence` was quietly promoted to `ongoing`.

Run `--calibrate` before trusting any preference number, and again after any
change to the judge prompt.

## Running it

```powershell
# calibrate the judges (judge calls only, reuses readings on disk)
python code/evaluation/model_to_model/run.py --calibrate --reuse-runs --limit 24

# adjudicate the labelled subset
python code/evaluation/model_to_model/run.py --samples-only

# adjudicate unlabelled requests, concentrating on real disagreement
python code/evaluation/model_to_model/run.py --limit 40 --only-disagreements
```

Both stages cost money. Stage 1 is two harness passes; stage 2 is two judge
passes over the items. `--reuse-runs` skips stage 1 entirely.

Output lands in `code/evaluation/reports/model_to_model/`: `scorecard.md`,
`calibration.md`, and the per-item `verdicts.jsonl` / `calibration.jsonl`.

## Measured so far

Judge calibration, 24 injected defects, both judges:

| Defect | Caught (each judge) |
|---|---|
| scope_inflation | 3/3 |
| amount_drift | 4/4 |
| scope_overreach | 5/5 |
| claim_invention | 6/6 |
| claim_omission | 5/6 |

46 of 48 verdicts correct. Both judges missed the same `claim_omission` item and
called it equivalent — a dropped marginal claim is the one defect that can be
defensible. The judges are sensitive to what they are being asked to detect.

Adjudication on the 25 samples:

| | Result |
|---|---|
| Items | 19 |
| Claim sets that differ | 12 |
| Differences that changed an output field | **1** |
| Verdict "equivalent" | 10–11 of 19 |
| Self-preference gap | +7% for both judges |

The headline is the third row. The providers disagree about *wording, scope
metadata and certainty labels* far more than they disagree about anything that
reaches `output.csv`, which is what the deterministic engine was built to
guarantee.

The most useful output is not the preference table but **"facts both readings
missed"** — items a judge flagged against both readings at once. No amount of
provider choice fixes those; they are the candidates for a prompt or claim
vocabulary change.
