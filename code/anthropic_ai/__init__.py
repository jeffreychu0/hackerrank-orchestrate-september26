"""Anthropic Messages API client, interchangeable with the open_ai package.

Named with an underscore because the code directory is on sys.path and a local
package called `anthropic` would shadow the installed SDK.
"""

from .client import AnthropicClient, ModelResult
from .config import Settings

__all__ = ["AnthropicClient", "ModelResult", "Settings"]
