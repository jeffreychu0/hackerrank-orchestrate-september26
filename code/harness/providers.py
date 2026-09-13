"""Provider selection: the one place the harness knows a vendor name.

Every provider client used here satisfies the same small contract:

    structured(system_prompt, chat_prompt, schema, *, images=(), schema_name="")
        -> (payload: dict, result: ModelResult)
    close() -> None

and `ModelResult` carries `text`, `response_id`, `model`, `input_tokens`,
`output_tokens`, `total_tokens`. Nothing else in `harness/` imports a vendor SDK
or a vendor package, so adding a provider means adding a row here.
"""

PROVIDERS = ("openai", "anthropic")

#: Published list prices per million tokens (input, output), used only for the
#: cost estimate in the usage report. Override per run with the CLI pricing flags.
PRICING = {
    "openai": (1.25, 10.0),
    "anthropic": (5.0, 25.0),
}

#: Per-model list prices, matched by prefix so a dated snapshot id resolves to
#: its family. A model absent here falls back to its provider's row above.
MODEL_PRICING = (
    ("claude-fable-5", (10.0, 50.0)),
    ("claude-mythos-5", (10.0, 50.0)),
    ("claude-opus-", (5.0, 25.0)),
    ("claude-sonnet-5", (2.0, 10.0)),
    ("claude-sonnet-4-6", (3.0, 15.0)),
    ("claude-haiku-", (1.0, 5.0)),
)


class UnknownProvider(ValueError):
    """A provider name outside the supported set."""


def normalise(provider):
    name = (provider or "openai").strip().lower()
    if name not in PROVIDERS:
        raise UnknownProvider("Unknown provider {!r}; choose one of: {}"
                              .format(provider, ", ".join(PROVIDERS)))
    return name


def default_pricing(provider, model=None):
    """List price for a model, falling back to the provider's default row."""
    if model:
        name = str(model).strip().lower()
        for prefix, price in MODEL_PRICING:
            if name.startswith(prefix):
                return price
    return PRICING[normalise(provider)]


def build_client(provider):
    """Construct the configured client for a provider.

    Imported lazily so a run against one provider never needs the other
    vendor's SDK installed or its credentials present.
    """
    name = normalise(provider)
    if name == "anthropic":
        from anthropic_ai import AnthropicClient, Settings
        return AnthropicClient(Settings.from_env())
    from open_ai import OpenAIClient, Settings
    return OpenAIClient(Settings.from_env())


def describe(client):
    """The model a client is configured for, for reports and logs."""
    return getattr(getattr(client, "settings", None), "model", "unknown")
