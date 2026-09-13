"""Single-turn text generation with explicit prompts and usage metadata."""

from dataclasses import dataclass

from openai import OpenAI

from .config import Settings
from .prompts import PromptPair


@dataclass(frozen=True)
class ModelResult:
    text: str
    response_id: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class OpenAIClient:
    def __init__(self, settings: Settings, *, sdk_client: OpenAI | None = None):
        self.settings = settings
        self._owns_client = sdk_client is None
        self._sdk = sdk_client if sdk_client is not None else OpenAI(
            api_key=settings.api_key,
            base_url="https://api.openai.com/v1",
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def prompt(self, system_prompt: str, chat_prompt: str) -> ModelResult:
        prompts = PromptPair(system=system_prompt, chat=chat_prompt)
        response = self._sdk.responses.create(
            model=self.settings.model,
            instructions=prompts.system,
            input=[{"role": "user", "content": prompts.chat}],
            max_output_tokens=self.settings.max_output_tokens,
            store=False,
        )
        if response.status != "completed":
            raise RuntimeError("OpenAI did not complete the response; check the token limit and model.")
        if not response.output_text.strip():
            raise RuntimeError("OpenAI returned no text (possibly a refusal or non-text response).")
        usage = response.usage
        return ModelResult(
            text=response.output_text,
            response_id=response.id,
            model=response.model,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
        )

    def close(self):
        if self._owns_client:
            self._sdk.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
