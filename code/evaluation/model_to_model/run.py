"""Run the cross-model evaluation end to end.

    python code/evaluation/model_to_model/run.py --limit 40
    python code/evaluation/model_to_model/run.py --reuse-runs --only-disagreements
    python code/evaluation/model_to_model/run.py --samples-only      # labelled subset
    python code/evaluation/model_to_model/run.py --calibrate --reuse-runs

``--calibrate`` runs a different experiment: instead of two real readings, it
pairs each real reading against the same reading damaged in one known way, so
the correct verdict is known by construction and each judge's sensitivity can be
measured. Run it before trusting any preference number, and after any change to
the judge prompt.

Stage 1 runs the harness once per provider so each has read the same evidence
independently. Stage 2 shows both readings, unlabelled, to each provider in
turn. Stage 3 scores preference, self-preference bias, judge agreement and -
where a published sample answer exists - whether the judges' preferences track
the producer that actually got the row right.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if __package__ in (None, ""):                    # allow running as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from evaluation.model_to_model import dataset, judge, perturb, score
else:
    from . import dataset, judge, perturb, score

from harness import interpret, providers, recurrence
from harness.config import DEFAULT_DATASET, REPORTS_DIR, HarnessConfig, RecurrencePolicy
from harness.ledger import EvidenceLoader
from harness.runner import Harness

OUT_DIR = REPORTS_DIR / "model_to_model"


def run_producer(provider, dataset_root, request_ids, workers):
    """One harness pass, leaving its audit trail and rows on disk."""
    predictions = OUT_DIR / "rows_{}.csv".format(provider)
    config = HarnessConfig(
        dataset=dataset_root, output=predictions, output_mirrors=(),
        usage_report=OUT_DIR / "usage_{}.md".format(provider),
        audit_log=OUT_DIR / "audit_{}.jsonl".format(provider),
        provider=provider, use_model=True, explain_with_model=False,
        include_samples=True, workers=workers, request_ids=tuple(request_ids))
    with Harness(config) as harness:
        report = harness.run()
    return predictions, config.audit_log, report


def evidence_for(loader, request_id, dataset_root):
    """Rebuild exactly what the producers saw, for the judge to see too."""
    bundle = loader.bundle(request_id)
    series = recurrence.detect(bundle, RecurrencePolicy())
    return (interpret.evidence_prompt(bundle, series),
            interpret.load_images(bundle, dataset_root))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--providers", nargs=2, default=list(providers.PROVIDERS),
                        metavar=("A", "B"))
    parser.add_argument("--limit", type=int, default=40,
                        help="Cap the number of adjudicated items")
    parser.add_argument("--samples-only", action="store_true",
                        help="Use the 25 published samples, so judges can be calibrated")
    parser.add_argument("--only-disagreements", action="store_true",
                        help="Adjudicate only where the two readings differ")
    parser.add_argument("--calibrate", action="store_true",
                        help="Judge real readings against deliberately damaged copies")
    parser.add_argument("--defect-source", default=None,
                        help="Which provider's readings to damage (default: the first)")
    parser.add_argument("--reuse-runs", action="store_true",
                        help="Reuse producer runs already on disk; no producer API calls")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    loader = EvidenceLoader(args.dataset, include_samples=True)
    sample_ids = _sample_ids(args.dataset)
    if args.samples_only:
        targets = sample_ids
    else:
        targets = [r for r in loader.request_ids if r not in set(sample_ids)]
        targets = targets[:args.limit * 3]      # headroom before filtering

    audits, rows = {}, {}
    producer_usage = {}
    for provider in args.providers:
        audit_path = args.out / "audit_{}.jsonl".format(provider)
        rows_path = args.out / "rows_{}.csv".format(provider)
        if not args.reuse_runs:
            print("stage 1: reading evidence with {} ({} requests)"
                  .format(provider, len(targets)))
            rows_path, audit_path, report = run_producer(
                provider, args.dataset, targets, args.workers)
            totals = report.usage.totals
            producer_usage[provider] = {
                "calls": totals.calls, "tokens": totals.total_tokens,
                "cost": report.usage.cost(totals)}
            print("   {} calls, {:,} tokens, ${:.4f}".format(
                totals.calls, totals.total_tokens, report.usage.cost(totals)))
        audits[provider] = dataset.load_audit(audit_path)
        rows[provider] = dataset.load_rows(rows_path)

    if args.calibrate:
        return _calibrate(args, audits, loader)

    items = dataset.build(audits, rows, providers=args.providers,
                          only_disagreements=args.only_disagreements,
                          limit=args.limit)
    summary = dataset.summarise(items)
    print("stage 2: adjudicating {} items".format(len(items)))
    if not items:
        print("nothing to adjudicate; try --limit higher or drop --only-disagreements")
        return 1

    evidence = {i.request_id: evidence_for(loader, i.request_id, args.dataset)
                for i in items}
    verdicts, judge_usage = [], {}
    for judge_provider in args.providers:
        client = providers.build_client(judge_provider)
        calls = tokens = 0
        cost_in, cost_out = providers.default_pricing(
            judge_provider, providers.describe(client))
        try:
            def adjudicate(item):
                text, images = evidence[item.request_id]
                return item, judge.adjudicate(client, item, text, images=images)

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                results = list(pool.map(_safe(adjudicate), items))
            for item, outcome in results:
                if outcome is None:
                    continue
                payload, usage = outcome
                calls += 1
                tokens += usage.total_tokens or 0
                cost_in_tokens = usage.input_tokens or 0
                cost_out_tokens = usage.output_tokens or 0
                judge_usage.setdefault(judge_provider, {"calls": 0, "tokens": 0,
                                                        "cost": 0.0})
                judge_usage[judge_provider]["cost"] += (
                    cost_in_tokens / 1e6 * cost_in + cost_out_tokens / 1e6 * cost_out)
                verdicts.append(_to_verdict(judge_provider, item, payload))
        finally:
            client.close()
        if judge_provider in judge_usage:
            judge_usage[judge_provider]["calls"] = calls
            judge_usage[judge_provider]["tokens"] = tokens
        print("   {} judged {} items".format(judge_provider, calls))

    truth = _sample_answers(args.dataset) if args.samples_only else None
    text = score.report(verdicts, args.providers, summary, usage=judge_usage,
                        truth_rows=truth, rows_by_provider=rows)
    report_path = args.out / "scorecard.md"
    report_path.write_text(text, encoding="utf-8")
    _write_verdicts(args.out / "verdicts.jsonl", verdicts)
    print()
    print(text)
    print("scorecard: {}".format(report_path))
    if producer_usage:
        total = sum(v["cost"] for v in producer_usage.values())
        total += sum(v["cost"] for v in judge_usage.values())
        print("total spend this run: ${:.4f} over {} items".format(total, len(items)))
    return 0


def _calibrate(args, audits, loader):
    """Measure each judge against defects whose correct verdict is known."""
    source = args.defect_source or args.providers[0]
    cases = perturb.build(audits, provider=source, limit=args.limit)
    if not cases:
        print("no readings with claims to damage; run the producers first")
        return 1
    print("stage 2: {} injected-defect items from {} readings ({})".format(
        len(cases), source, dict(perturb.coverage(cases))))

    evidence = {c.request_id: evidence_for(loader, c.request_id, args.dataset)
                for c in cases}
    results, records, usage = [], [], {}
    for judge_provider in args.providers:
        client = providers.build_client(judge_provider)
        cost_in, cost_out = providers.default_pricing(
            judge_provider, providers.describe(client))
        stats = {"calls": 0, "tokens": 0, "cost": 0.0}
        try:
            def adjudicate(case):
                text, images = evidence[case.request_id]
                # The undamaged reading takes position 1 or 2 by the same
                # per-request coin flip the main eval uses, so position cannot
                # stand in for correctness.
                clean_first = dataset._order(case.request_id, case.defect)
                item = dataset.Item(
                    request_id=case.request_id, producers=("clean", "damaged"),
                    reading_1=case.original if clean_first else case.damaged,
                    reading_2=case.damaged if clean_first else case.original,
                    claims_differ=True, row_fields_differ=())
                payload, used = judge.adjudicate(client, item, text, images=images)
                verdict = payload["verdict"]
                if verdict == "reading_1":
                    resolved = "clean" if clean_first else "damaged"
                elif verdict == "reading_2":
                    resolved = "damaged" if clean_first else "clean"
                else:
                    resolved = verdict
                return case, resolved, payload, used

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for outcome in pool.map(_safe_case(adjudicate), cases):
                    if outcome is None:
                        continue
                    case, resolved, payload, used = outcome
                    stats["calls"] += 1
                    stats["tokens"] += used.total_tokens or 0
                    stats["cost"] += ((used.input_tokens or 0) / 1e6 * cost_in
                                      + (used.output_tokens or 0) / 1e6 * cost_out)
                    results.append((judge_provider, case.defect, resolved))
                    records.append({"request_id": case.request_id,
                                    "defect": case.defect, "note": case.note,
                                    "judge": judge_provider, "resolved": resolved,
                                    "verdict": payload["verdict"],
                                    "confidence": payload.get("confidence", ""),
                                    "reasoning": payload.get("reasoning", "")})
        finally:
            client.close()
        usage[judge_provider] = stats
        print("   {} judged {} items".format(judge_provider, stats["calls"]))

    text = score.detection_report(results, perturb.DEFECTS)
    text += ("\n## Adjudication cost\n\n"
             "| Judge | Calls | Tokens | Est. cost |\n|---|---:|---:|---:|\n")
    for judge_provider, stats in usage.items():
        text += "| {} | {} | {:,} | ${:,.4f} |\n".format(
            judge_provider, stats["calls"], stats["tokens"], stats["cost"])
    path = args.out / "calibration.md"
    path.write_text(text, encoding="utf-8")
    with (args.out / "calibration.jsonl").open("w", encoding="utf-8",
                                               newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print()
    print(text)
    print("calibration: {}".format(path))
    print("total spend this run: ${:.4f}".format(sum(v["cost"] for v in usage.values())))
    return 0


def _safe_case(function):
    def wrapper(case):
        try:
            return function(case)
        except Exception as exc:
            print("   warning {}/{}: {}".format(case.request_id, case.defect,
                                                type(exc).__name__))
            return None
    return wrapper


def _safe(function):
    def wrapper(item):
        try:
            return function(item)
        except Exception as exc:                 # a failed verdict is dropped, not faked
            print("   warning {}: {}".format(item.request_id, type(exc).__name__))
            return item, None
    return wrapper


def _to_verdict(judge_provider, item, payload):
    winner = item.producer_of(payload["verdict"])
    defects = {item.producers[0]: payload.get("defects_in_reading_1", []),
               item.producers[1]: payload.get("defects_in_reading_2", [])}
    return score.Verdict(
        request_id=item.request_id, judge=judge_provider, winner=winner,
        confidence=payload.get("confidence", ""),
        reasoning=payload.get("reasoning", ""), defects=defects,
        missed_by_both=tuple(payload.get("missed_by_both", [])),
        claims_differ=item.claims_differ, row_fields_differ=item.row_fields_differ)


def _write_verdicts(path, verdicts):
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        for verdict in verdicts:
            handle.write(json.dumps({
                "request_id": verdict.request_id, "judge": verdict.judge,
                "winner": verdict.winner, "confidence": verdict.confidence,
                "claims_differ": verdict.claims_differ,
                "row_fields_differ": list(verdict.row_fields_differ),
                "reasoning": verdict.reasoning,
                "defects": {k: list(v) for k, v in verdict.defects.items()},
                "missed_by_both": list(verdict.missed_by_both),
            }, ensure_ascii=False) + "\n")


def _sample_ids(dataset_root):
    import csv
    with (Path(dataset_root) / "sample_requests.csv").open(encoding="utf-8-sig") as handle:
        return [row["request_id"] for row in csv.DictReader(handle)]


def _sample_answers(dataset_root):
    import csv
    with (Path(dataset_root) / "sample_requests.csv").open(encoding="utf-8-sig") as handle:
        return {row["request_id"]: row for row in csv.DictReader(handle)}


if __name__ == "__main__":
    raise SystemExit(main())
