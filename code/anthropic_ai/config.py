"""Explicit environment configuration; importing this module makes no API calls.

The package is named ``anthropic_ai`` rather than ``anthropic`` on purpose: the
code directory is on ``sys.path``, so a local package called ``anthropic`` would
shadow the installed SDK of the same name. This mirrors the existing ``open_ai``
package, which is spelled with an underscore for exactly the same reason.
"""

from dataclasses import dataclass, field
import math
import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

#: Anthropic's current default model. Override with ANTHROPIC_MODEL.
DEFAULT_MODEL = "claude-opus-5"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class Settings:
    """Everything the client needs, resolved once from the environment."""

    #: Blank is legitimate: the SDK resolves ANTHROPIC_AUTH_TOKEN, an `ant auth
    #: login` profile or workload identity federation on its own. Passing an
    #: empty key through would defeat that chain, so a blank key means "let the
    #: SDK decide" rather than "fail".
    api_key: str = field(repr=False, default="")
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 120
    max_retries: int = 2
    max_output_tokens: int = 4096
    #: Left unset by default so the request carries the API's own default rather
    #: than a level an older model would reject.
    effort: str = ""

    def __post_init__(self):
        if not self.model.strip():
            raise ValueError("Set ANTHROPIC_MODEL to a Messages API model, "
                             "for example {}.".format(DEFAULT_MODEL))
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("ANTHROPIC_TIMEOUT_SECONDS must be finite and positive.")
        if self.max_retries < 0:
            raise ValueError("ANTHROPIC_MAX_RETRIES must be zero or greater.")
        if self.max_output_tokens < 1:
            raise ValueError("ANTHROPIC_MAX_OUTPUT_TOKENS must be positive.")
        if self.effort and self.effort not in EFFORT_LEVELS:
            raise ValueError("ANTHROPIC_EFFORT must be one of: "
                             + ", ".join(EFFORT_LEVELS))

    @classmethod
    def from_env(cls, env_file: Path = DEFAULT_ENV_PATH):
        # Shell variables take precedence; no search of unrelated parent directories.
        load_dotenv(env_file, override=False)
        try:
            timeout = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "120"))
            retries = int(os.getenv("ANTHROPIC_MAX_RETRIES", "2"))
            tokens = int(os.getenv("ANTHROPIC_MAX_OUTPUT_TOKENS", "4096"))
        except ValueError:
            raise ValueError("Anthropic timeout, retry, and token settings "
                             "must be numeric.") from None
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL).strip(),
            timeout_seconds=timeout,
            max_retries=retries,
            max_output_tokens=tokens,
            effort=os.getenv("ANTHROPIC_EFFORT", "").strip(),
        )
