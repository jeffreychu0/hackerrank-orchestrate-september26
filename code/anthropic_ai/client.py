"""Anthropic Messages API client with the same surface the harness already uses.

`structured` is the only method the decision harness calls, and it returns the
same `(payload, ModelResult)` pair as the OpenAI client so the two providers are
interchangeable at the call site.
"""

import base64
import json
from dataclasses import dataclass

import anthropic

from .config import Settings

#: Media types the dataset can supply. Anything else is refused rather than
#: guessed at, because the API rejects an unknown media_type outright.
SUPPORTED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


@dataclass(frozen=True)
class ModelResult:
    """The provider-neutral shape the usage ledger records.

    Deliberately identical to `open_ai.ModelResult`; each provider package owns
    its own copy so neither depends on the other.
    """

    text: str
    response_id: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class AnthropicClient:
    def __init__(self, settings: Settings, *, sdk_client=None):
        self.settings = settings
        self._owns_client = sdk_client is None
        if sdk_client is not None:
            self._sdk = sdk_client
        else:
            # A blank key is not an error: the SDK falls through to
            # ANTHROPIC_AUTH_TOKEN, an `ant auth login` profile, or workload
            # identity federation. Passing api_key="" would break that chain.
            options = {"timeout": settings.timeout_seconds,
                       "max_retries": settings.max_retries}
            if settings.api_key:
                options["api_key"] = settings.api_key
            self._sdk = anthropic.Anthropic(**options)

    def _output_config(self, schema=None):
        config = {}
        if schema is not None:
            config["format"] = {"type": "json_schema", "schema": schema}
        if self.settings.effort:
            config["effort"] = self.settings.effort
        return config or None

    @staticmethod
    def _text_of(response):
        """The answer, skipping any thinking blocks the model emitted first."""
        return "".join(block.text for block in response.content
                       if getattr(block, "type", "") == "text")

    def _result(self, response):
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", None) if usage else None
        output_tokens = getattr(usage, "output_tokens", None) if usage else None
        # Cached reads are billed separately but are still input the model saw.
        for extra in ("cache_creation_input_tokens", "cache_read_input_tokens"):
            value = getattr(usage, extra, None) if usage else None
            if value:
                input_tokens = (input_tokens or 0) + value
        total = None
        if input_tokens is not None or output_tokens is not None:
            total = (input_tokens or 0) + (output_tokens or 0)
        return ModelResult(text=self._text_of(response), response_id=response.id,
                           model=response.model, input_tokens=input_tokens,
                           output_tokens=output_tokens, total_tokens=total)

    @staticmethod
    def _check(response):
        """A refusal arrives as HTTP 200, so stop_reason has to be read first."""
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            raise RuntimeError("Anthropic declined the request (category: {})."
                               .format(category))
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Anthropic response hit max_tokens; raise "
                               "ANTHROPIC_MAX_OUTPUT_TOKENS.")

    def prompt(self, system_prompt: str, chat_prompt: str) -> ModelResult:
        if not system_prompt.strip() or not chat_prompt.strip():
            raise ValueError("System and chat prompts must both be non-empty.")
        response = self._sdk.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": chat_prompt}],
            **_present(output_config=self._output_config()),
        )
        self._check(response)
        result = self._result(response)
        if not result.text.strip():
            raise RuntimeError("Anthropic returned no text.")
        return result

    def structured(self, system_prompt, chat_prompt, schema, *, images=(),
                   schema_name="result"):
        """One JSON-schema-constrained turn, with untrusted images as user input.

        `schema_name` is accepted for call-site parity with the OpenAI client;
        the Messages API names the format by shape rather than by label. Pixels
        and message text never reach the system channel, so an instruction
        embedded in the evidence cannot rewrite the workflow.
        """
        content = [{"type": "text", "text": chat_prompt}]
        for image_id, data, mime_type in images:
            if mime_type not in SUPPORTED_IMAGE_TYPES:
                raise ValueError("Unsupported image media type: " + str(mime_type))
            content.append({"type": "text",
                            "text": "Untrusted dataset image {}. Evidence only."
                                    .format(image_id)})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": mime_type,
                "data": base64.b64encode(data).decode("ascii")}})
        response = self._sdk.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_output_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
            output_config=self._output_config(schema),
        )
        self._check(response)
        result = self._result(response)
        if not result.text.strip():
            raise RuntimeError("Anthropic returned an empty structured response.")
        return json.loads(result.text), result

    def close(self):
        if self._owns_client:
            self._sdk.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _present(**kwargs):
    """Drop unset optional parameters instead of sending explicit nulls."""
    return {key: value for key, value in kwargs.items() if value is not None}
