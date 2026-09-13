"""End-to-end orchestration: evidence, interpretation, decision, output.csv.

One pass per request:

    load evidence  ->  detect recurrence  ->  model reads messages/images
        ->  validate claims  ->  rebuild recurrence  ->  deterministic forecast
        ->  candidate plans and permitted changes  ->  ranked decision
        ->  explanation  ->  contract validation  ->  row

Model failures degrade to the deterministic path for that request instead of
failing the run; every degradation is reported.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from open_ai import OpenAIClient, Settings

from . import decide, explain, facts, interpret, output, recurrence
from .config import REPO_ROOT, HarnessConfig
from .ledger import EvidenceLoader
from .usage import UsageLedger


@dataclass
class RequestOutcome:
    request_id: str
    row: dict
    contract_problems: tuple = ()
    rejected_facts: tuple = ()
    unresolved: tuple = ()
    warnings: tuple = ()
    used_model: bool = False
    accepted_facts: tuple = ()
    coverage: dict = field(default_factory=dict)


@dataclass
class RunReport:
    outcomes: list = field(default_factory=list)
    usage: UsageLedger = None
    written: int = 0

    @property
    def invalid(self):
        return [o for o in self.outcomes if o.contract_problems]

    @property
    def degraded(self):
        return [o for o in self.outcomes if o.warnings]


class Harness:
    """Owns the dataset, the optional model client and the usage ledger."""

    def __init__(self, config: HarnessConfig):
        self.config = config
        self.loader = EvidenceLoader(config.dataset,
                                     include_samples=config.include_samples,
                                     forecast_days=config.forecast_days)
        self.client = None
        self.usage = UsageLedger("openai", config.input_cost_per_mtok,
                                 config.output_cost_per_mtok)
        self._client_lock = threading.Lock()

    def __enter__(self):
        if self.config.use_model or self.config.explain_with_model:
            self.client = OpenAIClient(Settings.from_env())
        return self

    def __exit__(self, *_):
        if self.client is not None:
            self.client.close()

    def request_ids(self):
        if self.config.request_ids:
            return list(self.config.request_ids)
        return self.loader.request_ids

    def run_one(self, request_id) -> RequestOutcome:
        bundle = self.loader.bundle(request_id)
        series = recurrence.detect(bundle, self.config.recurrence)
        review = facts.FactReview()
        warnings = []
        used_model = False

        if self.client is not None and self.config.use_model and interpret.needs_model(bundle):
            try:
                review, result = interpret.interpret(self.client, bundle, series,
                                                     self.config.dataset)
                self.usage.record(request_id, "evidence_interpretation", result)
                used_model = True
            except Exception as exc:                      # degrade, never abort the run
                warnings.append("interpretation_failed: {}".format(_short(exc)))
                review = facts.FactReview()

        if review.accepted:
            bundle = facts.apply_event_facts(bundle, review)
            series = recurrence.detect(bundle, self.config.recurrence)
            series = facts.apply_series_facts(bundle, series, review)

        coverage = {
            "events": len(bundle.events),
            "messages": len(bundle.messages),
            "images": len(bundle.images),
            "payment_options": len(bundle.options),
            "series_detected": len(series),
            "unresolved_amounts": len(bundle.unknown_amount_event_ids),
        }
        decision = decide.decide(bundle, series,
                                 fact_summaries=review.summaries(), coverage=coverage)

        explanation = explain.template(decision, bundle)
        if self.client is not None and self.config.explain_with_model:
            try:
                text, result = explain.with_model(self.client, decision, bundle)
                self.usage.record(request_id, "decision_explanation", result)
                explanation = text
                used_model = True
            except Exception as exc:
                warnings.append("explanation_model_failed: {}".format(_short(exc)))

        row = decision.row(explanation)
        problems = output.validate_row(row, bundle)
        if problems:
            row = _safe_fallback(row, decision, bundle, problems)
        return RequestOutcome(request_id, row, tuple(problems),
                              tuple(reason for _, reason in review.rejected),
                              review.unresolved, tuple(warnings), used_model,
                              review.summaries(), coverage)

    def run(self) -> RunReport:
        ids = self.request_ids()
        outcomes = []
        if self.config.workers > 1 and self.client is not None:
            with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
                outcomes = list(pool.map(self.run_one, ids))
        else:
            outcomes = [self.run_one(request_id) for request_id in ids]
        report = RunReport(outcomes, self.usage)
        self.usage.requests_total = len(ids)
        rows = [o.row for o in outcomes]
        report.written = output.write(rows, self.config.output, ids)
        written_paths = [self.config.output]
        for mirror in self.config.output_mirrors:
            if Path(mirror) != Path(self.config.output):
                output.write(rows, Path(mirror), ids)
                written_paths.append(Path(mirror))
        self._write_audit(outcomes)
        deterministic = sum(1 for o in outcomes if not o.used_model)
        self.config.usage_report.parent.mkdir(parents=True, exist_ok=True)
        self.config.usage_report.write_text(
            self.usage.report(dataset_requests=len(ids),
                              deterministic_requests=deterministic,
                              outputs=[_relative(path) for path in written_paths]),
            encoding="utf-8")
        return report


    def _write_audit(self, outcomes):
        """One JSON line per request: what was read, believed, refused and decided."""
        path = self.config.audit_log
        if path is None:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for outcome in outcomes:
                handle.write(json.dumps({
                    "request_id": outcome.request_id,
                    "coverage": outcome.coverage,
                    "used_model": outcome.used_model,
                    "accepted_facts": list(outcome.accepted_facts),
                    "rejected_fact_reasons": list(outcome.rejected_facts),
                    "unresolved_questions": list(outcome.unresolved),
                    "warnings": list(outcome.warnings),
                    "contract_problems": list(outcome.contract_problems),
                    "decision": {key: outcome.row[key] for key in
                                 ("amount_safe_to_pay", "affordability_status",
                                  "recommended_payment_method", "payment_plan",
                                  "earliest_date_for_full_payment",
                                  "spending_changes_needed")},
                }, ensure_ascii=False) + "\n")


def _relative(path):
    """Report repository-relative paths rather than one machine's directory layout."""
    path = Path(path)
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _short(exc):
    text = " ".join(str(exc).split())
    return (text[:160] + "...") if len(text) > 160 else (text or type(exc).__name__)


def _safe_fallback(row, decision, bundle, problems):
    """Never emit a contract-breaking row: fall back to the conservative answer."""
    row = dict(row)
    row["affordability_status"] = "not_affordable"
    row["recommended_payment_method"] = "not_recommended"
    row["payment_plan"] = "none"
    row["spending_changes_needed"] = "none"
    if row["earliest_date_for_full_payment"] and \
            "affordable_now_requires_earliest_date_equal_to_request_date" in problems:
        pass
    row["decision_explanation"] = explain.template(
        decide.Decision(
            request_id=decision.request_id, amount_safe_to_pay=decision.amount_safe_to_pay,
            affordability_status="not_affordable", recommended_payment_method="not_recommended",
            payments=(), earliest_date_for_full_payment=None, spending_changes=(),
            currency=decision.currency, minimum_balance=decision.minimum_balance,
            projected_minimum=decision.projected_minimum,
            requested_amount=decision.requested_amount, deadline=decision.deadline,
            as_of=decision.as_of), bundle)
    return row
