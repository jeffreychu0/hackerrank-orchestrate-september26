"""Offline tests for the cross-model eval: blinding, bias maths, calibration."""

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.model_to_model import dataset, judge, score

PROVIDERS = ("openai", "anthropic")


def claim(fact_type="income_amount_change", amount="100.00", **extra):
    base = {"fact_type": fact_type, "source_ids": ["message_01"], "category": "salary",
            "event_ids": ["event_1"], "amount": amount, "effective_date": None,
            "period_days": None, "scope": "ongoing", "certainty": "confirmed",
            "rationale": "because", "unresolved_questions": []}
    base.update(extra)
    return base


def audit(request_id, claims, provider="openai"):
    return {"request_id": request_id, "provider": provider,
            "accepted_claims": claims, "accepted_facts": [],
            "rejected_fact_reasons": [], "unresolved_questions": [],
            "warnings": [], "contract_problems": [], "decision": {}}


def row(request_id, **fields):
    base = {"request_id": request_id, "amount_safe_to_pay": "100",
            "affordability_status": "affordable_now",
            "recommended_payment_method": "full_payment",
            "payment_plan": "2026-01-01:100",
            "earliest_date_for_full_payment": "2026-01-01",
            "spending_changes_needed": "none"}
    base.update(fields)
    return base


class DatasetTests(unittest.TestCase):
    def build(self, claims_a, claims_b, **kwargs):
        ids = list(claims_a)
        audits = {"openai": {r: audit(r, claims_a[r]) for r in ids},
                  "anthropic": {r: audit(r, claims_b[r], "anthropic") for r in ids}}
        rows = {p: {r: row(r) for r in ids} for p in PROVIDERS}
        return dataset.build(audits, rows, providers=PROVIDERS, **kwargs)

    def test_identical_claims_are_not_marked_as_differing(self):
        same = {"request_26": [claim()]}
        items = self.build(same, {"request_26": [claim()]})
        self.assertFalse(items[0].claims_differ)

    def test_claim_order_and_wording_do_not_count_as_a_difference(self):
        a = {"request_26": [claim(amount="1"), claim(amount="2")]}
        b = {"request_26": [claim(amount="2", rationale="different words"),
                            claim(amount="1", rationale="also different")]}
        self.assertFalse(self.build(a, b)[0].claims_differ)

    def test_a_changed_amount_is_a_difference(self):
        a = {"request_26": [claim(amount="1")]}
        b = {"request_26": [claim(amount="2")]}
        self.assertTrue(self.build(a, b)[0].claims_differ)

    def test_presentation_order_is_blinded_but_reproducible(self):
        ids = ["request_{}".format(n) for n in range(26, 70)]
        claims_a = {r: [claim(amount="1")] for r in ids}
        claims_b = {r: [claim(amount="2")] for r in ids}
        first = self.build(claims_a, claims_b)
        second = self.build(claims_a, claims_b)
        self.assertEqual([i.producers for i in first], [i.producers for i in second])
        leading = [i.producers[0] for i in first]
        # Both providers must appear in position one, or the order is a tell.
        self.assertIn("openai", leading)
        self.assertIn("anthropic", leading)

    def test_a_blind_verdict_maps_back_to_its_producer(self):
        item = self.build({"request_26": [claim(amount="1")]},
                          {"request_26": [claim(amount="2")]})[0]
        self.assertEqual(item.producer_of("reading_1"), item.producers[0])
        self.assertEqual(item.producer_of("reading_2"), item.producers[1])
        self.assertEqual(item.producer_of("equivalent"), "equivalent")

    def test_items_with_no_claims_on_either_side_are_dropped(self):
        self.assertEqual(self.build({"request_26": []}, {"request_26": []}), [])

    def test_only_disagreements_filters_agreeing_items(self):
        claims_a = {"request_26": [claim(amount="1")], "request_27": [claim()]}
        claims_b = {"request_26": [claim(amount="2")], "request_27": [claim()]}
        items = self.build(claims_a, claims_b, only_disagreements=True)
        self.assertEqual([i.request_id for i in items], ["request_26"])

    def test_output_impact_is_recorded_separately_from_claim_difference(self):
        ids = ["request_26"]
        audits = {"openai": {r: audit(r, [claim(amount="1")]) for r in ids},
                  "anthropic": {r: audit(r, [claim(amount="2")], "anthropic") for r in ids}}
        rows = {"openai": {r: row(r) for r in ids},
                "anthropic": {r: row(r, amount_safe_to_pay="999") for r in ids}}
        item = dataset.build(audits, rows, providers=PROVIDERS)[0]
        self.assertTrue(item.claims_differ)
        self.assertEqual(item.row_fields_differ, ("amount_safe_to_pay",))

    def test_summary_counts_claim_noise_that_changed_nothing(self):
        ids = ["request_26"]
        audits = {"openai": {r: audit(r, [claim(amount="1")]) for r in ids},
                  "anthropic": {r: audit(r, [claim(amount="2")], "anthropic") for r in ids}}
        rows = {p: {r: row(r) for r in ids} for p in PROVIDERS}
        items = dataset.build(audits, rows, providers=PROVIDERS)
        self.assertEqual(dataset.summarise(items)["claims_differ_without_output_change"], 1)

    def test_audit_round_trips_through_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audit.jsonl"
            path.write_text(json.dumps(audit("request_26", [claim()])) + "\n",
                            encoding="utf-8")
            self.assertIn("request_26", dataset.load_audit(path))


def verdict(request_id, judge_name, winner, **kwargs):
    return score.Verdict(request_id=request_id, judge=judge_name, winner=winner,
                         confidence=kwargs.pop("confidence", "high"), **kwargs)


class BiasMathTests(unittest.TestCase):
    def test_a_judge_that_always_picks_itself_shows_a_full_gap(self):
        verdicts = []
        for n in range(10):
            rid = "request_{}".format(n)
            verdicts.append(verdict(rid, "openai", "openai"))
            verdicts.append(verdict(rid, "anthropic", "anthropic"))
        stats = score.self_preference(verdicts, PROVIDERS)
        self.assertEqual(stats["openai"]["preferred_by_itself"], 1.0)
        self.assertEqual(stats["openai"]["preferred_by_the_other_judge"], 0.0)
        self.assertEqual(stats["openai"]["self_preference_gap"], 1.0)

    def test_judges_that_agree_show_no_gap(self):
        verdicts = []
        for n in range(10):
            rid = "request_{}".format(n)
            winner = "openai" if n % 2 else "anthropic"
            verdicts.append(verdict(rid, "openai", winner))
            verdicts.append(verdict(rid, "anthropic", winner))
        stats = score.self_preference(verdicts, PROVIDERS)
        self.assertEqual(stats["openai"]["self_preference_gap"], 0.0)
        self.assertEqual(stats["anthropic"]["self_preference_gap"], 0.0)

    def test_ties_are_excluded_from_the_bias_estimate(self):
        verdicts = [verdict("request_1", "openai", "equivalent"),
                    verdict("request_1", "anthropic", "neither")]
        stats = score.self_preference(verdicts, PROVIDERS)
        self.assertIsNone(stats["openai"]["self_preference_gap"])

    def test_judge_agreement_counts_only_items_both_judged(self):
        verdicts = [verdict("request_1", "openai", "openai"),
                    verdict("request_1", "anthropic", "openai"),
                    verdict("request_2", "openai", "anthropic")]
        stats = score.agreement_between_judges(verdicts, PROVIDERS)
        self.assertEqual(stats["items_judged_by_both"], 1)
        self.assertEqual(stats["identical_verdict"], 1)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.truth = {"request_1": row("request_1", amount_safe_to_pay="100"),
                      "request_2": row("request_2", amount_safe_to_pay="200")}
        self.rows = {
            "openai": {"request_1": row("request_1", amount_safe_to_pay="100"),
                       "request_2": row("request_2", amount_safe_to_pay="999")},
            "anthropic": {"request_1": row("request_1", amount_safe_to_pay="999"),
                          "request_2": row("request_2", amount_safe_to_pay="200")},
        }

    def test_a_judge_that_always_picks_the_right_producer_scores_one(self):
        verdicts = [verdict("request_1", "anthropic", "openai"),
                    verdict("request_2", "openai", "anthropic")]
        stats = score.calibration(verdicts, self.truth, self.rows, PROVIDERS,
                                  "amount_safe_to_pay")
        self.assertEqual(stats["discriminating_items"], 2)
        self.assertEqual(stats["rate"], 1.0)

    def test_items_where_both_producers_agree_carry_no_signal(self):
        rows = {p: {"request_1": row("request_1", amount_safe_to_pay="100")}
                for p in PROVIDERS}
        stats = score.calibration([verdict("request_1", "openai", "openai")],
                                  self.truth, rows, PROVIDERS, "amount_safe_to_pay")
        self.assertEqual(stats["discriminating_items"], 0)
        self.assertIsNone(stats["rate"])

    def test_requests_without_a_published_answer_are_skipped(self):
        stats = score.calibration([verdict("request_99", "openai", "openai")],
                                  self.truth, self.rows, PROVIDERS, "amount_safe_to_pay")
        self.assertEqual(stats["discriminating_items"], 0)


class JudgePromptTests(unittest.TestCase):
    def test_the_prompt_never_names_a_provider(self):
        item = dataset.Item(request_id="request_26", producers=PROVIDERS,
                            reading_1=[claim()], reading_2=[claim(amount="2")],
                            claims_differ=True, row_fields_differ=())
        text = judge.prompt_for(item, "EVIDENCE BLOCK")
        lowered = (text + judge.SYSTEM_PROMPT).lower()
        for name in ("openai", "anthropic", "gpt", "claude", "sonnet", "opus"):
            self.assertNotIn(name, lowered, name)

    def test_the_prompt_carries_the_evidence_and_both_readings(self):
        item = dataset.Item(request_id="request_26", producers=PROVIDERS,
                            reading_1=[claim()], reading_2=[], claims_differ=True,
                            row_fields_differ=())
        text = judge.prompt_for(item, "EVIDENCE BLOCK")
        self.assertIn("EVIDENCE BLOCK", text)
        self.assertIn("READING 1", text)
        self.assertIn("READING 2", text)
        self.assertIn("no claims", text)

    def test_the_schema_allows_abstention(self):
        allowed = judge.VERDICT_SCHEMA["properties"]["verdict"]["enum"]
        self.assertIn("equivalent", allowed)
        self.assertIn("neither", allowed)

    def test_the_judge_is_told_not_to_reward_verbosity(self):
        self.assertIn("More claims is not", judge.SYSTEM_PROMPT)


class ReportTests(unittest.TestCase):
    def test_a_scorecard_renders_without_ground_truth(self):
        verdicts = [verdict("request_1", "openai", "anthropic"),
                    verdict("request_1", "anthropic", "anthropic")]
        text = score.report(verdicts, PROVIDERS, {"items": 1})
        self.assertIn("Self-preference bias", text)
        self.assertIn("Judge agreement", text)
        self.assertNotIn("calibration", text.lower().split("## judge agreement")[0])


if __name__ == "__main__":
    unittest.main()
