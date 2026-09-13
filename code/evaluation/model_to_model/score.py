"""Scoring for the cross-model eval, including the checks that keep it honest.

Three things are measured, not one:

1. **Preference** - which producer's reading each judge preferred.
2. **Self-preference bias** - every item is judged by both models, so the gap
   between how often judge X prefers producer X and how often the *other* judge
   prefers producer X is a direct estimate of the bias, not an assumption
   about it.
3. **Judge calibration** - on requests that have a published sample answer, the
   preferred reading can be checked against which producer actually produced the
   correct output row. A judge that cannot beat a coin flip there is not
   evidence about anything.
"""

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Verdict:
    request_id: str
    judge: str                  # provider that judged
    winner: str                 # provider name, or "equivalent" / "neither"
    confidence: str
    reasoning: str = ""
    defects: dict = field(default_factory=dict)   # provider -> [defect, ...]
    missed_by_both: tuple = ()
    claims_differ: bool = False
    row_fields_differ: tuple = ()


def tally(verdicts, providers):
    """Per-judge preference counts."""
    table = {}
    for judge in providers:
        counts = Counter(v.winner for v in verdicts if v.judge == judge)
        table[judge] = {
            "judged": sum(counts.values()),
            **{p: counts.get(p, 0) for p in providers},
            "equivalent": counts.get("equivalent", 0),
            "neither": counts.get("neither", 0),
        }
    return table


def self_preference(verdicts, providers):
    """How much more often a judge picks its own family than the other judge does.

    Positive means the judge favours its own output. Measured only on items
    where a side actually won, since ties carry no preference signal.
    """
    first, second = providers
    decided = {j: [v for v in verdicts if v.judge == j and v.winner in providers]
               for j in providers}
    result = {}
    for producer in providers:
        rates = {}
        for judge in providers:
            pool = decided[judge]
            rates[judge] = (sum(1 for v in pool if v.winner == producer) / len(pool)
                            if pool else None)
        own, other = rates[producer], rates[second if producer == first else first]
        result[producer] = {
            "preferred_by_itself": own,
            "preferred_by_the_other_judge": other,
            "self_preference_gap": (None if own is None or other is None
                                    else round(own - other, 4)),
            "decided_items": {j: len(decided[j]) for j in providers},
        }
    return result


def agreement_between_judges(verdicts, providers):
    """How often the two judges reached the same verdict on the same item."""
    by_request = {}
    for verdict in verdicts:
        by_request.setdefault(verdict.request_id, {})[verdict.judge] = verdict
    both = [pair for pair in by_request.values() if len(pair) == len(providers)]
    if not both:
        return {"items_judged_by_both": 0}
    first, second = providers
    same = sum(1 for pair in both if pair[first].winner == pair[second].winner)
    decided = [pair for pair in both
               if pair[first].winner in providers and pair[second].winner in providers]
    same_decided = sum(1 for pair in decided
                       if pair[first].winner == pair[second].winner)
    return {
        "items_judged_by_both": len(both),
        "identical_verdict": same,
        "identical_verdict_rate": round(same / len(both), 4),
        "items_where_both_picked_a_side": len(decided),
        "agreed_when_both_picked_a_side": same_decided,
    }


def calibration(verdicts, truth_rows, rows_by_provider, providers, field_name):
    """Does the preferred reading match the producer that got the row right?

    Only requests with a published sample answer can be scored, and only those
    where exactly one producer got the field right discriminate at all.
    """
    scored = correct = 0
    for verdict in verdicts:
        if verdict.winner not in providers:
            continue
        want = truth_rows.get(verdict.request_id)
        if not want:
            continue
        right = [p for p in providers
                 if rows_by_provider[p].get(verdict.request_id, {}).get(field_name)
                 == want[field_name]]
        if len(right) != 1:
            continue        # both right or both wrong: no signal
        scored += 1
        correct += verdict.winner == right[0]
    return {
        "discriminating_items": scored,
        "judge_picked_the_correct_producer": correct,
        "rate": round(correct / scored, 4) if scored else None,
    }


def detection(results, defects):
    """Per-defect judge sensitivity.

    ``results`` is a list of ``(judge, defect, verdict)`` where ``verdict`` is
    "clean", "damaged", "equivalent" or "neither" after un-blinding. Only
    "clean" is correct: the undamaged reading really is the better one.
    """
    judges = sorted({judge for judge, _, _ in results})
    table = {}
    for defect in defects:
        row = {}
        for judge in judges:
            pool = [v for j, d, v in results if j == judge and d == defect]
            row[judge] = {
                "items": len(pool),
                "caught": sum(1 for v in pool if v == "clean"),
                "missed_as_equivalent": sum(1 for v in pool if v == "equivalent"),
                "preferred_the_damaged_reading": sum(1 for v in pool if v == "damaged"),
                "rate": round(sum(1 for v in pool if v == "clean") / len(pool), 4)
                        if pool else None,
            }
        table[defect] = row
    return table, judges


def detection_report(results, defects, *, models=None, source=None):
    """A markdown scorecard for the injected-defect calibration."""
    table, judges = detection(results, defects)
    lines = [
        "# Judge calibration on injected defects",
        "",
        "Each item pairs a real reading against the same reading damaged in one "
        "specific way. The undamaged reading is correct by construction, so a "
        "judge that cannot prefer it is not measuring evidence fidelity. These "
        "are the failure modes deterministic validation cannot catch: the "
        "validator already refuses an unknown source, an unowned event, an "
        "invented category or an impossible date.",
        "",
        "A verdict of \"equivalent\" counts as a miss - the two readings are "
        "not equivalent.",
    ]
    if source:
        lines += ["", "Damaged readings were derived from the **{}** run."
                  .format(source)]
    lines += _models_table(models)
    lines += [
        "",
        "| Defect | " + " | ".join("{} caught".format(j) for j in judges) + " | Items |",
        "|---|" + "---:|" * (len(judges) + 1),
    ]
    for defect in defects:
        row = table[defect]
        if not any(row[j]["items"] for j in judges):
            continue
        cells = []
        for judge in judges:
            stats = row[judge]
            cells.append("{}/{} ({})".format(stats["caught"], stats["items"],
                                             _pct(stats["rate"])))
        items = max(row[j]["items"] for j in judges)
        lines.append("| {} | {} | {} |".format(defect, " | ".join(cells), items))

    lines += ["", "## Where the misses went", "",
              "| Defect | Judge | Called it equivalent | Preferred the damaged reading |",
              "|---|---|---:|---:|"]
    for defect in defects:
        for judge in judges:
            stats = table[defect][judge]
            if not stats["items"] or stats["caught"] == stats["items"]:
                continue
            lines.append("| {} | {} | {} | {} |".format(
                defect, judge, stats["missed_as_equivalent"],
                stats["preferred_the_damaged_reading"]))
    lines.append("")
    return "\n".join(lines)


def defect_themes(verdicts, providers, top=8):
    """The most common criticisms levelled at each producer, verbatim."""
    themes = {}
    for producer in providers:
        counter = Counter()
        for verdict in verdicts:
            for defect in verdict.defects.get(producer, ()):
                counter[" ".join(str(defect).split())[:110]] += 1
        themes[producer] = counter.most_common(top)
    return themes


def _models_table(models):
    """Name the exact models, so a scorecard can never be read out of context."""
    if not models:
        return []
    lines = ["", "## Models", "", "| Role | Provider | Model |", "|---|---|---|"]
    for provider, model in models.items():
        lines.append("| producer and judge | {} | `{}` |".format(provider, model))
    return lines


def report(verdicts, providers, dataset_summary, *, usage=None, models=None,
           truth_rows=None, rows_by_provider=None):
    """A readable markdown scorecard."""
    first, second = providers
    counts = tally(verdicts, providers)
    lines = [
        "# Cross-model evaluation",
        "",
        "Each request's evidence was read independently by both providers, then "
        "both readings were shown - unlabelled and in a per-request randomised "
        "order - to each provider for adjudication. Every item is therefore "
        "judged once by a model that produced one of the readings and once by "
        "one that produced the other.",
    ]
    lines += _models_table(models)
    lines += [
        "",
        "## Eval set",
        "",
        "| Property | Count |",
        "|---|---:|",
    ]
    for key, value in dataset_summary.items():
        lines.append("| {} | {} |".format(key.replace("_", " "), value))

    lines += ["", "## Preference by judge", "",
              "| Judge | Items | Prefers {} | Prefers {} | Equivalent | Neither |"
              .format(first, second), "|---|---:|---:|---:|---:|---:|"]
    for judge in providers:
        row = counts[judge]
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            judge, row["judged"], row[first], row[second],
            row["equivalent"], row["neither"]))

    lines += ["", "## Self-preference bias", "",
              "A judge that rates its own reading higher than the other judge "
              "rates that same reading is showing self-preference. The gap is "
              "the estimate; it is not assumed to be zero.",
              "",
              "| Reading produced by | Preferred by itself | Preferred by the other judge | Gap |",
              "|---|---:|---:|---:|"]
    for producer, stats in self_preference(verdicts, providers).items():
        lines.append("| {} | {} | {} | {} |".format(
            producer, _pct(stats["preferred_by_itself"]),
            _pct(stats["preferred_by_the_other_judge"]),
            _signed(stats["self_preference_gap"])))

    lines += ["", "## Judge agreement", "", "| Property | Value |", "|---|---:|"]
    for key, value in agreement_between_judges(verdicts, providers).items():
        lines.append("| {} | {} |".format(key.replace("_", " "), value))

    if truth_rows and rows_by_provider:
        lines += ["", "## Judge calibration against the published answers", "",
                  "Requests that have a sample answer and where exactly one "
                  "producer got the field right. Anything near 50% means the "
                  "verdicts carry no information.",
                  "", "| Field | Discriminating items | Judge correct | Rate |",
                  "|---|---:|---:|---:|"]
        for field_name in ("amount_safe_to_pay", "affordability_status",
                           "recommended_payment_method"):
            stats = calibration(verdicts, truth_rows, rows_by_provider,
                                providers, field_name)
            lines.append("| {} | {} | {} | {} |".format(
                field_name, stats["discriminating_items"],
                stats["judge_picked_the_correct_producer"], _pct(stats["rate"])))

    lines += ["", "## Most common criticisms", ""]
    for producer, themes in defect_themes(verdicts, providers).items():
        lines.append("**{}**".format(producer))
        lines.append("")
        if not themes:
            lines.append("- none recorded")
        for text, count in themes:
            lines.append("- ({}x) {}".format(count, text))
        lines.append("")

    missed = Counter()
    for verdict in verdicts:
        for item in verdict.missed_by_both:
            missed[" ".join(str(item).split())[:110]] += 1
    if missed:
        lines += ["## Facts both readings missed", "",
                  "Flagged by a judge on both readings at once, so no amount of "
                  "provider choice would fix them. These are the candidates for "
                  "a prompt or vocabulary change.", ""]
        for text, count in missed.most_common(10):
            lines.append("- ({}x) {}".format(count, text))
        lines.append("")

    if usage:
        lines += ["## Adjudication cost", "", "| Judge | Calls | Tokens | Est. cost |",
                  "|---|---:|---:|---:|"]
        for judge, stats in usage.items():
            lines.append("| {} | {} | {:,} | ${:,.4f} |".format(
                judge, stats["calls"], stats["tokens"], stats["cost"]))
        lines.append("")
    return "\n".join(lines)


def _pct(value):
    return "n/a" if value is None else "{:.0%}".format(value)


def _signed(value):
    return "n/a" if value is None else "{:+.0%}".format(value)
