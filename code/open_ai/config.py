"""Explicit environment configuration; importing this module makes no API calls."""

from dataclasses import dataclass, field
import math
import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 60
    max_retries: int = 2
    max_output_tokens: int = 2048

    def __post_init__(self):
        if not self.api_key.strip():
            raise ValueError("Set OPENAI_API_KEY in the environment or code/.env.")
        if not self.model.strip():
            raise ValueError("Set OPENAI_MODEL to a Responses API model available to your project.")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be finite and positive.")
        if self.max_retries < 0:
            raise ValueError("OPENAI_MAX_RETRIES must be zero or greater.")
        if self.max_output_tokens < 1:
            raise ValueError("OPENAI_MAX_OUTPUT_TOKENS must be positive.")

    @classmethod
    def from_env(cls, env_file: Path = DEFAULT_ENV_PATH):
        # Shell variables take precedence; no search of unrelated parent directories.
        load_dotenv(env_file, override=False)
        try:
            timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
            retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
            tokens = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2048"))
        except ValueError:
            raise ValueError("OpenAI timeout, retry, and token settings must be numeric.") from None
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "").strip(),
            timeout_seconds=timeout,
            max_retries=retries,
            max_output_tokens=tokens,
        )
