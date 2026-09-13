"""Initial agent entry point: prompt OpenAI; dataset decisions come later."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from openai import APIConnectionError, APIStatusError

from open_ai import OpenAIClient, PromptPair, Settings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prompt the OpenAI Responses API.")
    system = parser.add_mutually_exclusive_group(required=True)
    system.add_argument("--system", help="Literal system instructions")
    system.add_argument("--system-file", type=Path, help="UTF-8 system prompt file")
    chat = parser.add_mutually_exclusive_group(required=True)
    chat.add_argument("--chat", help="Literal user prompt")
    chat.add_argument("--chat-file", type=Path, help="UTF-8 user prompt file")
    parser.add_argument("--variables-file", type=Path, help="JSON object of strings for ${name} templates")
    parser.add_argument("--json", action="store_true", help="Include response ID, model, and usage")
    args = parser.parse_args(argv)
    try:
        system_text = args.system_file.read_text(encoding="utf-8-sig") if args.system_file else args.system
        chat_text = args.chat_file.read_text(encoding="utf-8-sig") if args.chat_file else args.chat
        if args.variables_file:
            variables = json.loads(args.variables_file.read_text(encoding="utf-8-sig"))
            if not isinstance(variables, dict) or not all(isinstance(v, str) for v in variables.values()):
                raise ValueError("Prompt variables must be a JSON object with string values.")
            prompts = PromptPair.from_templates(system_text, chat_text, variables)
        else:
            prompts = PromptPair(system_text, chat_text)
        with OpenAIClient(Settings.from_env()) as client:
            result = client.prompt(prompts.system, prompts.chat)
        print(json.dumps(asdict(result), ensure_ascii=False) if args.json else result.text)
        return 0
    except APIStatusError as exc:
        # Do not print raw HTTP bodies, headers, or secrets.
        print(f"OpenAI HTTP {exc.status_code}: check credentials, model access, quota, and request settings.", file=sys.stderr)
    except APIConnectionError:
        print("Could not connect to OpenAI; check network access and timeout settings.", file=sys.stderr)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Configuration or response error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
