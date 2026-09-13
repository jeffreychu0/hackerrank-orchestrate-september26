"""Calibration: score the harness against the 25 supplied sample answers.

The sample answers are never available to the solution itself; this script reads
them only to report how closely the deterministic policy and the interpretation
layer reproduce the published decision style.

    python code/evaluate_samples.py                            # deterministic only
    python code/evaluate_samples.py --model                    # with interpretation
    python code/evaluate_samples.py --model --provider anthropic
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from harness.config import (DEFAULT_DATASET, DEFAULT_PROVIDER, REPORTS_DIR,
                            HarnessConfig)
from harness.providers import PROVIDERS
from harness.runner import Harness

FIELDS = ("affordability_status", "recommended_payment_method", "payment_plan",
          "earliest_date_for_full_payment", "spending_changes_needed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", action="store_true", help="Enable evidence interpretation")
    parser.add_argument("--provider", choices=PROVIDERS, default=DEFAULT_PROVIDER)
    parser.add_argument("--out", type=Path, default=None,
                        help="Write the produced rows here instead of the default scratch file")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    truth = {row["request_id"]: row for row in
             csv.DictReader((args.dataset / "sample_requests.csv").open(encoding="utf-8-sig"))}
    tag = args.provider if args.model else "deterministic"
    scratch = args.out or (REPORTS_DIR / "sample_predictions_{}.csv".format(tag))
    config = HarnessConfig(
        dataset=args.dataset, output=scratch,
        usage_report=scratch.with_name("sample_usage_{}.md".format(tag)),
        audit_log=scratch.with_name("sample_audit_{}.jsonl".format(tag)),
        output_mirrors=(), use_model=args.model, explain_with_model=False,
        include_samples=True, provider=args.provider,
        workers=args.workers if args.model else 1, request_ids=tuple(truth))
    with Harness(config) as harness:
        report = harness.run()

    hits = dict.fromkeys(FIELDS, 0)
    hits["amount_within_1pct"] = 0
    error = Decimal(0)
    for outcome in report.outcomes:
        want = truth[outcome.request_id]
        got = outcome.row
        for field in FIELDS:
            hits[field] += got[field] == want[field]
        requested = Decimal(want["requested_amount"]) or Decimal(1)
        relative = abs(Decimal(got["amount_safe_to_pay"])
                       - Decimal(want["amount_safe_to_pay"])) / requested
        error += relative
        hits["amount_within_1pct"] += relative < Decimal("0.01")
        if not args.quiet:
            flags = "".join("." if got[f] == want[f] else "X" for f in FIELDS)
            print("{:11} {} rel={:.3f} got={}/{} want={}/{}".format(
                outcome.request_id, flags, float(relative),
                got["affordability_status"], got["recommended_payment_method"],
                want["affordability_status"], want["recommended_payment_method"]))

    total = len(report.outcomes)
    print()
    for field, count in hits.items():
        print("{:34} {:>3}/{}".format(field, count, total))
    print("{:34} {:.4f}".format("mean relative amount error", float(error / total)))
    print("{:34} {:>3}/{}".format("exact on all five fields",
                                  sum(1 for o in report.outcomes
                                      if all(o.row[f] == truth[o.request_id][f] for f in FIELDS)),
                                  total))
    usage = report.usage.totals
    if usage.calls:
        print("{:34} {} calls, {:,} tokens, ${:.4f}".format(
            "model usage", usage.calls, usage.total_tokens,
            report.usage.cost(usage)))
        print("{:34} {}".format("models", ", ".join(sorted(report.usage.by_model))))
    for outcome in report.degraded:
        print("warning {}: {}".format(outcome.request_id, "; ".join(outcome.warnings)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
