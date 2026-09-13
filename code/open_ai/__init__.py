"""Reusable text interface to the OpenAI Responses API."""

from .client import ModelResult, OpenAIClient
from .config import Settings
from .prompts import PromptPair

__all__ = ["ModelResult", "OpenAIClient", "Settings", "PromptPair"]
