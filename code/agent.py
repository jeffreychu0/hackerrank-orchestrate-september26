"""Run one request through the dataset-tool agent (draft evidence analysis)."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from openai import APIConnectionError, APIStatusError
from open_ai import OpenAIClient, Settings
from tools import DatasetStore, build_registry
from tools.dataset import DEFAULT_DATASET


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--include-samples", action="store_true", help="Load sample input fields only, never answers")
    parser.add_argument("--max-model-calls", type=int, default=12)
    parser.add_argument("--max-tool-calls", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        registry = build_registry(DatasetStore(args.dataset, include_samples=args.include_samples), args.request_id)
        system = (Path(__file__).resolve().parent / "prompts" / "decision_system.md").read_text(encoding="utf-8")
        with OpenAIClient(Settings.from_env()) as client:
            result = client.run_agent(registry, system,
                f"Analyze the active request {args.request_id}. Retrieve its supporting evidence and explain eligible plans and outstanding safety checks.",
                max_model_calls=args.max_model_calls, max_tool_calls=args.max_tool_calls)
        print(json.dumps(asdict(result), ensure_ascii=False) if args.json else result.text)
        return 0
    except APIStatusError as exc:
        print(f"OpenAI HTTP {exc.status_code}; check model access, quota and settings.", file=sys.stderr)
    except APIConnectionError:
        print("Unable to connect to OpenAI.", file=sys.stderr)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Agent error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
