"""Run the sample check on two providers and report where they differ.

    python code/compare_providers.py                       # openai vs anthropic
    python code/compare_providers.py --reuse               # score CSVs already on disk

Each provider run is scored against the published sample answers, then the two
sets of rows are diffed against each other so provider disagreement is visible
separately from disagreement with the samples.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path

import evaluate_samples
from harness.config import DEFAULT_DATASET, REPORTS_DIR
from harness.providers import PROVIDERS

FIELDS = ("amount_safe_to_pay", "affordability_status", "recommended_payment_method",
          "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed")
SCORED = FIELDS[1:]


def load(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        return {row["request_id"]: row for row in csv.DictReader(handle)}


def agreement(rows, truth):
    """How many of the five judged fields each provider got right."""
    hits = dict.fromkeys(SCORED, 0)
    error = Decimal(0)
    exact = 0
    for request_id, row in rows.items():
        want = truth[request_id]
        for field in SCORED:
            hits[field] += row[field] == want[field]
        exact += all(row[field] == want[field] for field in SCORED)
        requested = Decimal(want["requested_amount"]) or Decimal(1)
        error += abs(Decimal(row["amount_safe_to_pay"])
                     - Decimal(want["amount_safe_to_pay"])) / requested
    return hits, exact, error / max(len(rows), 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--providers", nargs=2, default=list(PROVIDERS),
                        metavar=("A", "B"))
    parser.add_argument("--reuse", action="store_true",
                        help="Score existing prediction CSVs instead of calling the API")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args(argv)

    truth = load(args.dataset / "sample_requests.csv")
    results, usages = {}, {}
    for provider in args.providers:
        path = REPORTS_DIR / "sample_predictions_{}.csv".format(provider)
        if not args.reuse:
            print("=" * 72)
            print("running {}".format(provider))
            evaluate_samples.main(["--model", "--provider", provider, "--quiet",
                                   "--dataset", str(args.dataset),
                                   "--workers", str(args.workers)])
        results[provider] = load(path)
        usages[provider] = path.with_name("sample_usage_{}.md".format(provider))

    first, second = args.providers
    print("=" * 72)
    print("{:34} {:>14} {:>14}".format("agreement with the samples", first, second))
    scores = {p: agreement(results[p], truth) for p in args.providers}
    for field in SCORED:
        print("{:34} {:>14} {:>14}".format(
            field, "{}/25".format(scores[first][0][field]),
            "{}/25".format(scores[second][0][field])))
    print("{:34} {:>14} {:>14}".format("all five fields exact",
                                       "{}/25".format(scores[first][1]),
                                       "{}/25".format(scores[second][1])))
    print("{:34} {:>14.4f} {:>14.4f}".format("mean relative amount error",
                                             float(scores[first][2]),
                                             float(scores[second][2])))

    print()
    print("provider disagreement (rows where the two differ):")
    differing = 0
    for request_id in sorted(results[first], key=lambda r: int(r.split("_")[1])):
        a, b = results[first][request_id], results[second][request_id]
        deltas = [f for f in FIELDS if a[f] != b[f]]
        if not deltas:
            continue
        differing += 1
        want = truth[request_id]
        print("  {}".format(request_id))
        for field in deltas:
            marks = ("" if field not in SCORED else
                     "  [{} correct]".format(first if a[field] == want[field]
                                             else second if b[field] == want[field]
                                             else "neither"))
            print("    {:32} {} -> {}{}".format(field, a[field], b[field], marks))
    print("  {} of {} requests differ between providers".format(differing, len(truth)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
