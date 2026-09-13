"""Bounded Responses tool loop; no provider-specific code in dataset tools."""

from dataclasses import dataclass

from tools.core import ToolRegistry
from .config import Settings
from .prompts import PromptPair
from .tools_adapter import result_items, tool_schemas


@dataclass(frozen=True)
class AgentResult:
    text: str
    response_id: str
    model: str
    model_calls: int
    tool_calls: int
    usage: list[dict]
    tool_trace: list[dict]
    cash_flow_validated: bool = False


def run_agent(sdk, settings: Settings, registry: ToolRegistry, system: str, chat: str,
              *, max_model_calls=12, max_tool_calls=40) -> AgentResult:
    if not 1 <= max_model_calls <= 50 or not 1 <= max_tool_calls <= 200:
        raise ValueError("Model calls must be 1..50 and tool calls 1..200.")
    prompts = PromptPair(system, chat)
    history = [{"role": "user", "content": prompts.chat}]
    usage, trace = [], []
    for round_number in range(1, max_model_calls + 1):
        response = sdk.responses.create(
            model=settings.model, instructions=prompts.system, input=history,
            tools=tool_schemas(registry), store=False,
            include=["reasoning.encrypted_content"],
            max_output_tokens=settings.max_output_tokens,
        )
        usage.append({"response_id": response.id, "model": response.model,
                      "input_tokens": response.usage.input_tokens if response.usage else None,
                      "output_tokens": response.usage.output_tokens if response.usage else None,
                      "total_tokens": response.usage.total_tokens if response.usage else None})
        if response.status != "completed":
            raise RuntimeError("Agent response incomplete; increase output-token allowance or check model status.")
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if not response.output_text.strip():
                raise RuntimeError("Agent returned no final text.")
            return AgentResult(response.output_text, response.id, response.model,
                               round_number, len(trace), usage, trace)
        if len(trace) + len(calls) > max_tool_calls:
            raise RuntimeError("Agent tool-call budget exhausted; no decision was validated.")
        if round_number == max_model_calls:
            raise RuntimeError("Agent model-call budget exhausted before final response.")
        # Preserve reasoning and function-call items for stateless continuation.
        history.extend(response.output)
        outputs, attachments = [], []
        for call in calls:
            result = registry.execute(call.name, call.arguments)
            items = result_items(call.call_id, result)
            outputs.append(items[0])
            attachments.extend(items[1:])
            trace.append({"tool": call.name, "call_id": call.call_id,
                          "ok": result.data.get("ok", True)})
        history.extend(outputs)
        history.extend(attachments)
    raise RuntimeError("Agent exhausted its model-call budget.")
