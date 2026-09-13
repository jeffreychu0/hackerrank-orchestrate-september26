# Request-scoped dataset tools

The tool layer implements evidence retrieval and deterministic static checks for the workflow in [SAMPLE_ANALYSIS.md](../../docs/SAMPLE_ANALYSIS.md). It is independent of OpenAI: tool definitions use JSON Schema, handlers accept plain arguments, and results contain JSON-compatible data plus optional image bytes.

## Run the agent

From the repository root, using the existing `code/.env` and installed requirements:

```powershell
python code/agent.py --request-id request_26 --json
```

This makes live model calls. `OPENAI_MODEL` remains your configured model (currently GPT-5.4 in this checkout); no model setting was changed. Use an image-capable Responses model for image tools. `--max-model-calls` defaults to 12 and `--max-tool-calls` to 40. SDK retries may make additional HTTP attempts. Increase `OPENAI_MAX_OUTPUT_TOKENS` if a complex reasoning response exhausts its allowance; incomplete runs fail instead of being presented as completed decisions.

For a public example, enable input-only sample access explicitly:

```powershell
python code/agent.py --request-id request_03 --include-samples --json
```

Example output labels are stripped before indexing and never exposed to the model. By default only evaluation requests are indexed. The dataset root is resolved from the code location, so invocation does not depend on the working directory. `--dataset` permits a host-selected alternate dataset for fixtures or another checkout; tools cannot choose filenames themselves.

## Available tools

Every registry is bound to one request. No model argument can switch users or requests.

| Tool | Inputs | Result |
| --- | --- | --- |
| get_request | None | Eight request fields, as-of date, 90-day horizon |
| get_profile | None | Balance, minimum, priorities, protected categories, permitted changes and payment methods |
| get_events | category, status, offset, limit | Paginated raw financial events; nullable filters |
| get_event | event_id | Owned event, lifecycle parent/children, associated image IDs |
| get_commitments | offset, limit | Protected/fixed/pending/scheduled debit review candidates with selection reasons |
| get_spending_candidates | offset, limit | Non-protected flexible rows and actions the profile permits |
| get_payment_options | None | Exact dated offer schedules, fees, static rejection reasons, partial/wait permissions |
| get_messages | None | Request and user-level messages through request date, ordered by timestamp; future-message IDs noted |
| list_images | None | Linked image metadata and actual file availability |
| read_image | image_id | PNG bytes and source metadata, delivered as untrusted visual input |
| get_event_exchange_rate | event_id | Exact settlement-date currency direction and rate, even for blank image-derived amounts |
| convert_event_currency | event_id | Exact Decimal conversion of a known event amount; no premature rounding |

Use `{}` for tools with no inputs. Page sizes are 1-100; start at offset 0 and follow next_offset until null. All declared arguments are required in tool calls; use null for unused category/status filters. Unknown tools, malformed arguments, extra keys, cross-user IDs, missing images, and missing FX rates return `{ "ok": false, "error": "..." }` without giving access to arbitrary files. Unexpected I/O or programming failures propagate to the host rather than silently producing financial facts.

Monetary source fields remain strings to preserve decimal precision and unknown values. A blank amount is not zero. Source labels and IDs accompany results. Tool outputs are detached copies so callers cannot mutate loaded facts accidentally. Image bytes are returned separately from text, with a 15 MiB limit, PNG signature validation, and resolved path containment checks. No OCR values are hardcoded.

## Provider-neutral usage

From a module under `code/`:

```python
from tools import DatasetStore, build_registry

store = DatasetStore()  # Share this loaded store across sequential request runs.
registry = build_registry(store, "request_26")
result = registry.execute("get_profile", {})
print(result.data)
events = registry.execute("get_events", {
    "category": None, "status": None, "offset": 0, "limit": 100,
})
```

Other providers can translate `registry.definitions` into their function/tool format and call the same `execute(name, arguments)` dispatcher. `ToolResult.images` contains provider-neutral attachments. The minimal runtime schema validator intentionally supports only the object/string/integer/null subset currently declared; extend both validation and schema support before registering more complex tools.

The OpenAI translation lives in `code/open_ai/tools_adapter.py`, not in this package. `OpenAIClient.run_agent` uses the bounded loop in `code/open_ai/agent.py`. It sends strict function schemas, executes named tools, returns results with the matching call_id, and carries prior output/reasoning items forward with encrypted reasoning support for stateless continuation. Images are appended as user multimodal inputs after function results. System instructions are re-sent each model call and never constructed from dataset messages.

The runner returns per-call model/usage records and a compact tool-name/status trace, without persisting prompts or image bytes. Final JSON includes `cash_flow_validated: false`. Usage for failed or budget-exhausted runs is not yet persisted; this is not the completed submission's full-run usage report.

## Workflow and current boundaries

The trusted system workflow is [decision_system.md](../prompts/decision_system.md): reconstruct evidence, reserve commitments, consider accepted no-change plans, consider permitted cuts only if needed, and rank by the challenge's strict ordering. The optional 40/30/20/10 weights are not used.

This version retrieves facts and expands offers; it does **not** yet implement the full deterministic recurrence engine, essential-spending forecast, daily balance simulator, candidate partial/wait plan generator, or final output validator. Accordingly the CLI produces draft evidence analysis, not verified output.csv rows. A tool returning passes_static_checks does not establish affordability.

Commitment candidates include historical, failed, and cancelled rows to support reconciliation. They are not an additive expense total, nor a complete classification of essentials. Spending candidates establish permissions but do not establish recurrence or future savings. Do not replay historical settled movements into the current balance, count pending credits, or mistake investment valuations for cash. Currency conversion does not change a record's cash status.

Messages use date-only as-of filtering because requests have no time of day. Images may not carry dates in metadata; inspect the visual date and related event. Event retrieval preserves supplied future records and statuses for reconciliation rather than claiming independently authenticated as-of knowledge. For the supplied 28/30/31-day installment schedules, the static duration check compares payment count with max_installment_months; a different schedule convention needs an explicit policy before reuse elsewhere.

## Verification

```powershell
python -m unittest discover -s code/tests -t code -v
python code/smoke_tools.py
```

Unit tests are offline: they check scoping, sample-label exclusion, pagination, missing amounts, FX direction/date, permissions, fees/schedules, images, invalid tool calls, continuation state, usage, and call-budget exhaustion using the real SDK with intercepted HTTP.

The live smoke test makes a small tool round-trip with the configured model: it must actually call get_request and return request_26. It does not attempt a full financial decision. The ordinary prompt smoke test remains `python code/smoke_test.py`.

Protocol reference: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling).
