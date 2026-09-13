"""Buy or Wait? entry point: run the harness over dataset/requests.csv.

    python code/main.py                         # full run, writes output.csv
    python code/main.py --provider anthropic    # same run through Claude
    python code/main.py --no-model              # deterministic only, no API calls
    python code/main.py --request-id request_07 --dry-run --verbose

Secrets come from the environment or code/.env only; nothing is printed.
"""

import argparse
import sys
from pathlib import Path

from harness.config import (DEFAULT_DATASET, DEFAULT_OUTPUT,
                            DEFAULT_OUTPUT_MIRRORS, DEFAULT_PROVIDER,
                            DEFAULT_USAGE_REPORT, FORECAST_DAYS, HarnessConfig)
from harness.providers import PROVIDERS
from harness.runner import Harness


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET,
                        help="Directory holding the participant-facing CSVs")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Where to write the predictions CSV (repository root by default)")
    parser.add_argument("--no-mirror", action="store_true",
                        help="Skip the dataset/output.csv copy of the predictions")
    parser.add_argument("--usage-report", type=Path, default=DEFAULT_USAGE_REPORT,
                        help="Where to write evaluation/usage_report.md")
    parser.add_argument("--request-id", action="append", default=[],
                        help="Limit the run to these request ids (repeatable)")
    parser.add_argument("--include-samples", action="store_true",
                        help="Also allow sample request ids as targets (input fields only)")
    parser.add_argument("--provider", choices=PROVIDERS, default=DEFAULT_PROVIDER,
                        help="Which vendor interprets the messages and images")
    parser.add_argument("--no-model", action="store_true",
                        help="Deterministic run: no evidence interpretation, no API calls")
    parser.add_argument("--explain", choices=("template", "model"), default="template",
                        help="Explanation writer; both use the same locked computed fields")
    parser.add_argument("--forecast-days", type=int, default=FORECAST_DAYS)
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel requests when the model is in use")
    parser.add_argument("--input-cost-per-mtok", type=float, default=None,
                        help="Override the provider list price used in the report")
    parser.add_argument("--output-cost-per-mtok", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print rows without writing output.csv")
    parser.add_argument("--verbose", action="store_true",
                        help="Print each produced row and every degradation")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = HarnessConfig(
        dataset=args.dataset, output=args.output, usage_report=args.usage_report,
        forecast_days=args.forecast_days, use_model=not args.no_model,
        explain_with_model=(args.explain == "model" and not args.no_model),
        provider=args.provider, workers=max(1, args.workers),
        request_ids=tuple(args.request_id),
        include_samples=args.include_samples or bool(args.request_id),
        output_mirrors=() if args.no_mirror else DEFAULT_OUTPUT_MIRRORS,
        input_cost_per_mtok=args.input_cost_per_mtok,
        output_cost_per_mtok=args.output_cost_per_mtok)
    if args.dry_run:
        # A rehearsal must not overwrite the artifacts of the real run.
        config = _replace(config, output=Path(config.output).with_suffix(".dryrun.csv"),
                          output_mirrors=(),
                          usage_report=Path(config.usage_report).with_suffix(".dryrun.md"),
                          audit_log=Path(config.audit_log).with_suffix(".dryrun.jsonl")
                          if config.audit_log else None)
    try:
        with Harness(config) as harness:
            report = harness.run()
    except (OSError, ValueError, RuntimeError) as exc:
        print("Run failed: {}".format(exc), file=sys.stderr)
        return 1
    except Exception as exc:      # provider SDK errors differ per vendor
        print("{} call failed ({}): check credentials, model access and quota, "
              "or run with --no-model.".format(args.provider, type(exc).__name__),
              file=sys.stderr)
        return 1

    if args.verbose:
        for outcome in report.outcomes:
            row = outcome.row
            print("{} {:<20} {:<16} safe={:<14} plan={} changes={}".format(
                row["request_id"], row["affordability_status"],
                row["recommended_payment_method"], row["amount_safe_to_pay"],
                row["payment_plan"], row["spending_changes_needed"]))
    for outcome in report.degraded:
        print("warning {}: {}".format(outcome.request_id, "; ".join(outcome.warnings)),
              file=sys.stderr)
    for outcome in report.invalid:
        print("contract violation {}: {}".format(outcome.request_id,
                                                 "; ".join(outcome.contract_problems)),
              file=sys.stderr)

    totals = report.usage.totals
    print("Wrote {} rows to {}".format(report.written, config.output))
    print("Model calls {} | input {:,} | output {:,} | total {:,} tokens".format(
        totals.calls, totals.input_tokens, totals.output_tokens, totals.total_tokens))
    print("Usage report: {}".format(config.usage_report))
    if report.invalid:
        print("{} row(s) failed contract validation.".format(len(report.invalid)),
              file=sys.stderr)
        return 2
    return 0


def _replace(config, **updates):
    from dataclasses import replace
    return replace(config, **updates)


if __name__ == "__main__":
    raise SystemExit(main())
