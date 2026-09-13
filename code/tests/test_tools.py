import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from open_ai import OpenAIClient, Settings
from open_ai.tools_adapter import tool_schemas, result_items
from tools import DatasetStore, build_registry
from tools.core import ToolError
from tests.test_open_ai import response_body


class DatasetToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = DatasetStore(include_samples=True)

    def registry(self, request="request_33"):
        return build_registry(self.store, request)

    def test_sample_answers_are_never_exposed(self):
        result = self.registry("request_01").execute("get_request", {})
        self.assertEqual(len(result.data["request"]), 8)
        self.assertNotIn("amount_safe_to_pay", result.data["request"])
        self.assertNotIn("decision_explanation", result.data["request"])
        with self.assertRaises(ToolError):
            build_registry(DatasetStore(), "request_01")

    def test_cross_user_event_and_image_are_rejected(self):
        registry = self.registry()
        for name, args in [("get_event", {"event_id": "event_01"}),
                           ("read_image", {"image_id": "image_01"}),
                           ("read_image", {"image_id": "../../.env"})]:
            self.assertFalse(registry.execute(name, args).data["ok"])

    def test_strict_arguments_and_unknown_tool(self):
        registry = self.registry()
        cases = [("shell", {}), ("get_profile", {"user_id": "user_01"}),
                 ("get_events", {"category": None, "status": None, "offset": 0, "limit": 101}),
                 ("get_events", {"category": None, "status": None, "offset": True, "limit": 10}),
                 ("get_request", "not-json"), ("get_request", "[]")]
        for name, args in cases:
            with self.subTest(name=name, args=args):
                self.assertFalse(registry.execute(name, args).data["ok"])

    def test_pagination_covers_every_event_once_and_preserves_unknown(self):
        registry = self.registry()
        offset, rows = 0, []
        while offset is not None:
            page = registry.execute("get_events", {"category": None, "status": None, "offset": offset, "limit": 7}).data
            rows.extend(page["rows"])
            offset = page["next_offset"]
        self.assertEqual(len(rows), len(self.store.events_by_user["user_33"]))
        self.assertEqual(len({r["event_id"] for r in rows}), len(rows))
        self.assertEqual(next(r["amount"] for r in rows if r["event_id"] == "event_3051"), "")
        self.assertTrue(all(r["user_id"] == "user_33" for r in rows))

    def test_results_are_detached_from_loaded_data(self):
        registry = self.registry()
        result = registry.execute("get_profile", {})
        result.data["profile"]["current_available_balance"] = "0"
        self.assertNotEqual(registry.execute("get_profile", {}).data["profile"]["current_available_balance"], "0")

    def test_messages_include_user_level_evidence_and_exclude_future(self):
        registry = self.registry("request_88")
        self.assertIn("message_67", [r["message_id"] for r in registry.execute("get_messages", {}).data["rows"]])
        future = {"user_id": "user_88", "request_id": "", "message_id": "future", "sent_at": "2099-01-01T00:00:00Z"}
        with patch.object(self.store, "messages", self.store.messages + [future]):
            result = registry.execute("get_messages", {}).data
            self.assertIn("future", result["excluded_future_message_ids"])
            self.assertNotIn("future", [r["message_id"] for r in result["rows"]])

    def test_exact_fx_and_non_cash_or_missing_amount_rejected(self):
        result = self.registry("request_25").execute("convert_event_currency", {"event_id": "event_2288"}).data
        self.assertEqual(result["converted_amount"], "28499994.00")
        self.assertEqual(result["settlement_date"], "2024-03-15")
        self.assertFalse(self.registry("request_22").execute("convert_event_currency", {"event_id": "event_1960"}).data["ok"])
        self.assertFalse(self.registry().execute("convert_event_currency", {"event_id": "event_3051"}).data["ok"])
        with patch.object(self.store, "rates", {}):
            self.assertFalse(self.registry("request_25").execute("convert_event_currency", {"event_id": "event_2288"}).data["ok"])

    def test_rate_lookup_for_blank_image_amount(self):
        result = self.registry("request_78").execute("get_event_exchange_rate", {"event_id": "event_7307"}).data
        self.assertTrue(result["ok"])
        self.assertEqual((result["from_currency"], result["to_currency"], result["rate"]), ("USD", "INR", "83.33"))
        self.assertEqual(result["settlement_date"], "2025-10-01")

    def test_options_preserve_fees_preferences_and_dates(self):
        result = self.registry("request_12").execute("get_payment_options", {}).data
        selected = next(o for o in result["options"] if o["payment_option_id"] == "payment_option_33")
        self.assertTrue(selected["passes_static_checks"])
        self.assertFalse(selected["cash_flow_validated"])
        self.assertEqual(selected["schedule"][-1], {"date": "2026-06-20", "amount": "22590.19"})
        full = next(o for o in result["options"] if o["payment_method"] == "full_payment")
        self.assertIn("payment_method_not_accepted", full["ineligibility_reasons"])
        self.assertFalse(result["partial_payment_permitted"])

    def test_commitment_candidates_preserve_protected_and_pending(self):
        result = self.registry("request_20").execute("get_commitments", {"offset": 0, "limit": 100}).data
        rows = result["rows"]
        self.assertTrue(any("protected_category" in r["review_reasons"] for r in rows))
        # Retrieve all pages if the first does not reach the recent pending records.
        while result["next_offset"] is not None:
            result = self.registry("request_20").execute("get_commitments", {"offset": result["next_offset"], "limit": 100}).data
            rows += result["rows"]
        bill = next(r for r in rows if r["event_id"] == "event_1786")
        self.assertEqual(bill["amount"], "")
        self.assertIn("pending_or_scheduled_debit", bill["review_reasons"])

    def test_spending_candidates_respect_permissions(self):
        rows = self.registry("request_21").execute("get_spending_candidates", {"offset": 0, "limit": 100}).data["rows"]
        self.assertIn("stop", next(r for r in rows if r["event_id"] == "event_1815")["permitted_actions"])
        self.assertIn("reduce_to", next(r for r in rows if r["event_id"] == "event_1816")["permitted_actions"])
        self.assertFalse(any(r["category"] in {"rent", "utilities", "groceries"} for r in rows))

    def test_images_are_attached_as_pixels_and_missing_files_fail(self):
        registry = self.registry()
        result = registry.execute("read_image", {"image_id": "image_06"})
        self.assertTrue(result.images[0].data.startswith(b"\x89PNG"))
        encoded = result_items("call_image", result)
        self.assertEqual(encoded[0]["type"], "function_call_output")
        self.assertEqual(encoded[1]["role"], "user")
        self.assertTrue(encoded[1]["content"][1]["image_url"].startswith("data:image/png;base64,"))
        with patch.object(Path, "is_file", return_value=False):
            self.assertFalse(registry.execute("read_image", {"image_id": "image_06"}).data["ok"])

    def test_openai_schemas_have_no_extra_properties(self):
        schemas = tool_schemas(self.registry())
        self.assertEqual(len(schemas), 12)
        for schema in schemas:
            self.assertTrue(schema["strict"])
            self.assertFalse(schema["parameters"]["additionalProperties"])
            self.assertEqual(set(schema["parameters"]["required"]), set(schema["parameters"]["properties"]))


class AgentLoopTests(unittest.TestCase):
    def run_fake(self, *, max_model_calls=3, bad_tool=False, image=False):
        requests = []
        def handler(request):
            payload = json.loads(request.content)
            requests.append(payload)
            body = response_body(text="Draft evidence report")
            if len(requests) == 1:
                body["output"] = [{"type": "reasoning", "id": "rs_test", "summary": [], "encrypted_content": "encrypted-test"},
                    {"type": "function_call", "id": "fc_test", "call_id": "call_1",
                     "name": "unknown" if bad_tool else "read_image" if image else "get_request",
                     "arguments": json.dumps({"image_id": "image_06"}) if image else "{}", "status": "completed"}]
            return httpx.Response(200, json=body)
        sdk = OpenAI(api_key="test-key", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(sdk.close)
        client = OpenAIClient(Settings(api_key="test-key", model="test-model"), sdk_client=sdk)
        result = client.run_agent(build_registry(DatasetStore(), "request_33"), "trusted-system", "analyze", max_model_calls=max_model_calls)
        return result, requests

    def test_tool_loop_returns_data_and_preserves_reasoning_instructions_usage(self):
        result, requests = self.run_fake()
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.tool_calls, 1)
        self.assertFalse(result.cash_flow_validated)
        self.assertEqual(sum(r["total_tokens"] for r in result.usage), 24)
        self.assertEqual(requests[1]["instructions"], "trusted-system")
        self.assertFalse(requests[1]["store"])
        history = requests[1]["input"]
        self.assertTrue(any(r.get("type") == "reasoning" and r["encrypted_content"] == "encrypted-test" for r in history))
        output = next(r for r in history if r.get("type") == "function_call_output")
        self.assertEqual(output["call_id"], "call_1")
        self.assertEqual(json.loads(output["output"])["request"]["request_id"], "request_33")

    def test_tool_errors_return_to_model(self):
        result, requests = self.run_fake(bad_tool=True)
        self.assertFalse(result.tool_trace[0]["ok"])
        output = next(r for r in requests[1]["input"] if r.get("type") == "function_call_output")
        self.assertFalse(json.loads(output["output"])["ok"])

    def test_multimodal_tool_output_reaches_sdk(self):
        _, requests = self.run_fake(image=True)
        self.assertTrue(any(r.get("role") == "user" and isinstance(r.get("content"), list)
                            and any(c["type"] == "input_image" for c in r["content"]) for r in requests[1]["input"]))

    def test_budget_exhaustion_raises_instead_of_returning_fake_final(self):
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            self.run_fake(max_model_calls=1)


if __name__ == "__main__":
    unittest.main()
