"""Keep trusted instructions separate from user content."""

from dataclasses import dataclass
from string import Template
from typing import Mapping


@dataclass(frozen=True)
class PromptPair:
    system: str
    chat: str

    def __post_init__(self):
        if not self.system.strip() or not self.chat.strip():
            raise ValueError("System and chat prompts must both be non-empty.")

    @classmethod
    def from_templates(
        cls, system_template: str, chat_template: str, variables: Mapping[str, str]
    ):
        """Strict, single-pass ${name} substitution; use $$ for literal dollars.

        Templates are trusted application text. Insert untrusted evidence into
        the chat template only. Inserted values are never parsed as templates.
        """
        try:
            system = Template(system_template).substitute(variables)
            chat = Template(chat_template).substitute(variables)
        except KeyError as exc:
            raise ValueError(f"Missing prompt variable: {exc.args[0]}") from None
        except ValueError:
            raise ValueError("Invalid prompt template; use ${name} or $$ for literal dollars.") from None
        return cls(system=system, chat=chat)
