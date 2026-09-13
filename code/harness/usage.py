"""Token and cost accounting for the run that produced output.csv."""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ModelUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens


class UsageLedger:
    """Thread-safe totals, split by provider, model and purpose."""

    def __init__(self, provider, input_cost_per_mtok, output_cost_per_mtok):
        self.provider = provider
        self.input_cost_per_mtok = input_cost_per_mtok
        self.output_cost_per_mtok = output_cost_per_mtok
        self._lock = threading.Lock()
        self.by_model = defaultdict(ModelUsage)
        self.by_purpose = defaultdict(ModelUsage)
        self.requests_with_calls = set()
        self.requests_total = 0
        self.started = datetime.now(timezone.utc)

    def record(self, request_id, purpose, result):
        with self._lock:
            for bucket in (self.by_model[result.model], self.by_purpose[purpose]):
                bucket.calls += 1
                bucket.input_tokens += result.input_tokens or 0
                bucket.output_tokens += result.output_tokens or 0
            self.requests_with_calls.add(request_id)

    @property
    def totals(self):
        combined = ModelUsage()
        for usage in self.by_model.values():
            combined.calls += usage.calls
            combined.input_tokens += usage.input_tokens
            combined.output_tokens += usage.output_tokens
        return combined

    def cost(self, usage):
        return (usage.input_tokens / 1e6 * self.input_cost_per_mtok
                + usage.output_tokens / 1e6 * self.output_cost_per_mtok)

    def report(self, *, dataset_requests, deterministic_requests, outputs=()):
        totals = self.totals
        per_request = (totals.total_tokens / dataset_requests) if dataset_requests else 0
        lines = [
            "# Token usage and cost report",
            "",
            "Final full-dataset run that produced {}.".format(
                ", ".join("`{}`".format(path) for path in outputs) or "the predictions CSV"),
            "",
            "| Field | Value |",
            "|---|---|",
            "| Run started (UTC) | {} |".format(self.started.strftime("%Y-%m-%d %H:%M:%S")),
            "| Provider | {} |".format(self.provider),
            "| Models used | {} |".format(", ".join(sorted(self.by_model)) or "none"),
            "| Evaluation requests | {} |".format(dataset_requests),
            "| Requests answered without any model call | {} |".format(deterministic_requests),
            "| Requests with at least one model call | {} |".format(len(self.requests_with_calls)),
            "| Total model calls | {} |".format(totals.calls),
            "| Input tokens | {:,} |".format(totals.input_tokens),
            "| Output tokens | {:,} |".format(totals.output_tokens),
            "| Total tokens | {:,} |".format(totals.total_tokens),
            "| Average tokens per request | {:,.1f} |".format(per_request),
            "| Estimated total cost (USD) | ${:,.4f} |".format(self.cost(totals)),
            "| Estimated cost per request (USD) | ${:,.6f} |".format(
                self.cost(totals) / dataset_requests if dataset_requests else 0),
            "",
            "Pricing assumption: ${:.2f} per million input tokens and ${:.2f} per million "
            "output tokens.".format(self.input_cost_per_mtok, self.output_cost_per_mtok),
            "",
            "## Per model",
            "",
            "| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | "
            "Est. cost (USD) |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for model in sorted(self.by_model):
            usage = self.by_model[model]
            lines.append("| {} | {} | {} | {:,} | {:,} | {:,} | ${:,.4f} |".format(
                self.provider, model, usage.calls, usage.input_tokens,
                usage.output_tokens, usage.total_tokens, self.cost(usage)))
        lines += ["", "## Per purpose", "",
                  "| Purpose | Calls | Input tokens | Output tokens | Total tokens | "
                  "Est. cost (USD) |", "|---|---:|---:|---:|---:|---:|"]
        for purpose in sorted(self.by_purpose):
            usage = self.by_purpose[purpose]
            lines.append("| {} | {} | {:,} | {:,} | {:,} | ${:,.4f} |".format(
                purpose, usage.calls, usage.input_tokens, usage.output_tokens,
                usage.total_tokens, self.cost(usage)))
        lines += ["",
                  "Deterministic forecasting, plan generation, ranking and output validation "
                  "use no tokens. The model is called only to interpret supplied messages and "
                  "images, so requests with no such evidence cost nothing.",
                  "",
                  "No API keys, credentials or configuration values are recorded here.",
                  ""]
        return "\n".join(lines)
