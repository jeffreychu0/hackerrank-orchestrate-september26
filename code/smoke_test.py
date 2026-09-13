"""Explicit live check: python code/smoke_test.py (one billable model call)."""

from contextlib import redirect_stdout
import io
import json
import sys

from main import main


if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        status = main([
            "--system", "Reply with exactly the user's message, with no additions.",
            "--chat", "OPENAI_ENDPOINT_OK",
            "--json",
        ])
    if status:
        raise SystemExit(status)
    result = json.loads(output.getvalue())
    print(json.dumps(result))
    if result["text"].strip() != "OPENAI_ENDPOINT_OK":
        print("Endpoint responded, but the expected echo did not match.", file=sys.stderr)
        raise SystemExit(1)
    print("Live endpoint smoke test passed.")
