"""Offline tests for the deterministic harness: no key, no network, no charges."""

import unittest
from datetime import date, timedelta
from decimal import Decimal

from harness import changes, decide, explain, facts, forecast, output, plans, recurrence
from harness.config import RecurrencePolicy
from harness.ledger import EvidenceLoader
from harness.money import normalized, plan_amount, quantize

DATASET = __import__("harness.config", fromlist=["DEFAULT_DATASET"]).DEFAULT_DATASET
LOADER = EvidenceLoader(DATASET, include_samples=True)
POLICY = RecurrencePolicy()


def bundle(request_id):
    return LOADER.bundle(request_id)


class MoneyFormatTests(unittest.TestCase):
    def test_amount_safe_to_pay_strips_trailing_zeros(self):
        self.assertEqual(normalized(Decimal("603.30")), "603.3")
        self.assertEqual(normalized(Decimal("25256.00")), "25256")
        self.assertEqual(normalized(Decimal("0")), "0")

    def test_plan_amounts_use_two_decimals_only_when_fractional(self):
        self.assertEqual(plan_amount(Decimal("620.4")), "620.40")
        self.assertEqual(plan_amount(Decimal("25256")), "25256")
        self.assertEqual(plan_amount(Decimal("23.5")), "23.50")

    def test_explanation_groups_thousands(self):
        self.assertEqual(explain.money(Decimal("15952906.67"), "IDR"), "IDR 15,952,906.67")
        self.assertEqual(explain.money(Decimal("18000"), "ZAR"), "ZAR 18,000")


class EvidenceTests(unittest.TestCase):
    def test_bundle_scopes_to_one_user_and_request(self):
        data = bundle("request_01")
        self.assertEqual(data.user_id, "user_01")
        self.assertTrue(all(row["user_id"] == "user_01" for row in data.messages))
        self.assertTrue(all(row["request_id"] == "request_01" for row in data.options))

    def test_future_messages_are_not_visible_at_the_request_date(self):
        data = bundle("request_06")
        self.assertTrue(all(row["sent_at"][:10] <= data.as_of.isoformat()
                            for row in data.messages))

    def test_non_cash_and_failed_rows_carry_an_exclusion_reason(self):
        data = bundle("request_22")
        for event in data.events:
            if event.status in ("cancelled", "failed", "unrealized"):
                self.assertTrue(event.exclusion_reason, event.event_id)

    def test_blank_amount_is_unknown_not_zero(self):
        data = bundle("request_03")
        for event_id in data.unknown_amount_event_ids:
            self.assertIsNone(data.event(event_id).amount)

    def test_foreign_currency_uses_the_settlement_date_rate(self):
        rate = LOADER.convert(Decimal("100"), "USD", "USD", date(2024, 1, 1))
        self.assertEqual(rate, Decimal("100"))
        self.assertIsNone(LOADER.convert(Decimal("100"), "USD", "INR", date(1999, 1, 1)))


class RecurrenceTests(unittest.TestCase):
    def test_payroll_wordings_form_one_income_stream(self):
        self.assertEqual(recurrence.income_stream("Payroll credit"), "payroll")
        self.assertEqual(recurrence.income_stream("Next confirmed salary"), "payroll")
        self.assertEqual(recurrence.income_stream("Prorated first salary"), "payroll")

    def test_other_income_kinds_stay_separate(self):
        self.assertEqual(recurrence.income_stream("Quarterly performance bonus"),
                         "variable_incentive")
        self.assertEqual(recurrence.income_stream("Delivery platform payout"),
                         "platform_earnings")
        self.assertNotEqual(recurrence.income_stream("Second household income"), "payroll")

    def test_monthly_series_keep_their_day_of_month(self):
        anchor = date(2026, 1, 31)
        self.assertEqual(recurrence.add_months(anchor, 1), date(2026, 2, 28))
        self.assertEqual(recurrence.add_months(anchor, 2), date(2026, 3, 31))

    def test_detected_series_are_grounded_in_the_user_history(self):
        data = bundle("request_06")
        series = recurrence.detect(data, POLICY)
        self.assertTrue(series)
        owned = {event.event_id for event in data.events}
        for item in series:
            self.assertIn(item.last_event_id, owned)
            self.assertGreaterEqual(item.occurrences, POLICY.min_occurrences)

    def test_lapsed_pattern_is_not_projected(self):
        data = bundle("request_13")
        series = recurrence.detect(data, POLICY)
        lapsed = [s for s in series if s.suppressed_reason == "pattern_lapsed_before_request_date"]
        self.assertTrue(lapsed, "user_13 has an income stream that stopped before the request")


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.bundle = bundle("request_01")
        self.series = recurrence.detect(self.bundle, POLICY)
        self.forecast = forecast.build(self.bundle, self.series)

    def test_path_starts_at_the_supplied_balance(self):
        self.assertEqual(self.forecast.path()[0][1], self.bundle.opening_balance)

    def test_safe_amount_is_capped_by_the_request(self):
        safe = self.forecast.safe_amount_today(self.bundle.requested_amount)
        self.assertLessEqual(safe, self.bundle.requested_amount)
        self.assertGreaterEqual(safe, Decimal("0"))

    def test_paying_the_safe_amount_keeps_the_floor(self):
        safe = self.forecast.safe_amount_today(self.bundle.requested_amount)
        self.assertTrue(self.forecast.supports_payments([(self.bundle.as_of, safe)]))

    def test_paying_one_unit_more_than_headroom_breaks_the_floor(self):
        headroom = self.forecast.headroom()
        self.assertFalse(self.forecast.supports_payments(
            [(self.bundle.as_of, headroom + Decimal("1"))]))

    def test_same_day_credits_land_before_debits(self):
        base = forecast.Forecast(Decimal("100"), Decimal("0"), date(2026, 1, 1),
                                 date(2026, 1, 31))
        day = date(2026, 1, 10)
        trial = base.with_flows([forecast.Flow(day, Decimal("-150"), "record", "bill"),
                                 forecast.Flow(day, Decimal("200"), "record", "salary")])
        self.assertEqual(trial.minimum_balance(), Decimal("100"))

    def test_pending_credits_are_never_counted(self):
        for request_id in ("request_10", "request_20"):
            data = bundle(request_id)
            projection = forecast.build(data, recurrence.detect(data, POLICY))
            sources = {flow.source_id for flow in projection.flows}
            for event in data.events:
                if event.status == "pending" and event.direction == "credit":
                    self.assertNotIn(event.event_id, sources)

    def test_earliest_full_payment_is_none_when_nothing_is_ever_safe(self):
        base = forecast.Forecast(Decimal("100"), Decimal("100"), date(2026, 1, 1),
                                 date(2026, 3, 31))
        self.assertIsNone(base.earliest_full_payment_date(Decimal("500")))


class PlanTests(unittest.TestCase):
    def test_option_schedule_uses_the_supplied_day_interval(self):
        option = {"payment_amount": "100", "number_of_payments": "3",
                  "first_payment_date": "2026-01-31", "payment_frequency_days": "31"}
        schedule = plans.schedule_for(option, date(2026, 1, 31))
        self.assertEqual([when for when, _ in schedule],
                         [date(2026, 1, 31), date(2026, 3, 3), date(2026, 4, 3)])

    def test_unaccepted_methods_are_rejected(self):
        data = bundle("request_01")     # user_01 accepts full_payment only
        for review in plans.review_options(data):
            if review.method == "installments":
                self.assertIn("payment_method_not_accepted", review.reasons)

    def test_installment_count_respects_the_month_limit(self):
        data = bundle("request_05")     # user_05 allows four months of installments
        for review in plans.review_options(data):
            if review.method == "installments" and len(review.payments) > 4:
                self.assertIn("exceeds_max_installment_months", review.reasons)

    def test_ranking_prefers_no_changes_over_lower_cost(self):
        cheap_with_cuts = plans.Candidate("installments", ((date(2026, 1, 1), Decimal("10")),),
                                          Decimal("10"), "payment_option_02",
                                          changes=("cut",))
        dearer_clean = plans.Candidate("installments", ((date(2026, 1, 1), Decimal("99")),),
                                       Decimal("99"), "payment_option_01")
        self.assertIs(plans.best([cheap_with_cuts, dearer_clean]), dearer_clean)

    def test_ranking_falls_through_to_the_lowest_option_id(self):
        first = plans.Candidate("installments", ((date(2026, 1, 1), Decimal("50")),),
                                Decimal("50"), "payment_option_07")
        second = plans.Candidate("installments", ((date(2026, 1, 1), Decimal("50")),),
                                 Decimal("50"), "payment_option_61")
        self.assertIs(plans.best([second, first]), first)

    def test_on_time_plans_outrank_late_ones(self):
        late = plans.Candidate("wait", ((date(2026, 5, 1), Decimal("10")),), Decimal("10"),
                               on_time=False)
        on_time = plans.Candidate("installments", ((date(2026, 1, 1), Decimal("99")),),
                                  Decimal("99"), "payment_option_01")
        self.assertIs(plans.best([late, on_time]), on_time)


class SpendingChangeTests(unittest.TestCase):
    def test_candidates_respect_protection_and_permission(self):
        data = bundle("request_21")
        series = recurrence.detect(data, POLICY)
        for option in changes.candidates(data, series):
            self.assertNotIn(option.category, data.protected_categories)
            if option.action == "stop":
                self.assertIn(option.category, data.stoppable_categories)
            else:
                self.assertIn(option.category, data.reducible_categories)

    def test_candidates_are_ordered_least_intrusive_first(self):
        data = bundle("request_21")
        found = changes.candidates(data, recurrence.detect(data, POLICY))
        savings = [option.saving for option in found]
        self.assertEqual(savings, sorted(savings))

    def test_reduction_never_goes_below_the_supplied_minimum(self):
        data = bundle("request_21")
        for option in changes.candidates(data, recurrence.detect(data, POLICY)):
            if option.action == "reduce_to":
                event = data.event(option.event_id)
                self.assertEqual(option.new_amount, quantize(event.minimum_allowed_amount))

    def test_rendering_matches_the_output_contract(self):
        stop = changes.SpendingChange("stop", "event_14", "streaming",
                                      Decimal("19"), Decimal("0"))
        reduce_to = changes.SpendingChange("reduce_to", "event_21", "dining",
                                           Decimal("47"), Decimal("23.5"))
        self.assertEqual(changes.render_all([stop, reduce_to]),
                         "stop:event_14|reduce_to:event_21:23.50")
        self.assertEqual(changes.render_all([]), "none")


class FactValidationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = bundle("request_06")
        self.source = self.bundle.messages[0]["message_id"]

    def review(self, **overrides):
        raw = {"fact_type": "income_amount_change", "source_ids": [self.source],
               "category": "salary", "event_ids": [], "amount": 1000,
               "effective_date": None, "period_days": None, "scope": "ongoing",
               "certainty": "confirmed", "rationale": "", "unresolved_questions": []}
        raw.update(overrides)
        return facts.validate(self.bundle, [raw])

    def test_a_well_formed_claim_is_accepted(self):
        self.assertEqual(len(self.review().accepted), 1)

    def test_unknown_source_is_rejected(self):
        self.assertEqual(self.review(source_ids=["message_999"]).rejected[0][1],
                         "source_id_not_in_supplied_evidence")

    def test_event_from_another_user_is_rejected(self):
        self.assertEqual(self.review(event_ids=["event_1"]).rejected[0][1],
                         "event_id_not_owned_by_user")

    def test_invented_category_is_rejected(self):
        self.assertEqual(self.review(category="crypto").rejected[0][1],
                         "category_absent_from_user_history")

    def test_unconfirmed_cash_increase_is_rejected(self):
        self.assertEqual(self.review(certainty="likely").rejected[0][1],
                         "cash_increasing_claim_is_not_confirmed")

    def test_unknown_fact_type_is_rejected(self):
        self.assertEqual(self.review(fact_type="transfer_funds").rejected[0][1],
                         "unknown_fact_type")

    def test_date_outside_history_and_forecast_is_rejected(self):
        self.assertEqual(self.review(effective_date="1999-01-01").rejected[0][1],
                         "effective_date_outside_history_and_forecast")

    def test_payroll_cannot_be_stopped_without_naming_the_pattern(self):
        series = recurrence.detect(self.bundle, POLICY)
        payroll = [s for s in series if s.stream == "payroll"]
        self.assertTrue(payroll)
        review = facts.validate(self.bundle, [{
            "fact_type": "exclude_projection", "source_ids": [self.source],
            "category": "salary", "event_ids": [], "amount": None,
            "effective_date": None, "period_days": None, "scope": "ongoing",
            "certainty": "confirmed", "rationale": "", "unresolved_questions": []}])
        applied = facts.apply_series_facts(self.bundle, series, review)
        self.assertTrue(all(s.active for s in applied if s.stream == "payroll"))

    def test_naming_the_pattern_does_stop_it(self):
        series = recurrence.detect(self.bundle, POLICY)
        payroll = [s for s in series if s.stream == "payroll"][0]
        review = facts.validate(self.bundle, [{
            "fact_type": "income_stream_ends", "source_ids": [self.source],
            "category": payroll.category, "event_ids": [payroll.last_event_id],
            "amount": None, "effective_date": None, "period_days": None,
            "scope": "ongoing", "certainty": "confirmed", "rationale": "",
            "unresolved_questions": []}])
        applied = facts.apply_series_facts(self.bundle, series, review)
        self.assertFalse([s for s in applied if s.stream == "payroll"][0].active)

    def test_image_amount_fills_only_a_blank_row(self):
        data = bundle("request_03")
        blank = data.unknown_amount_event_ids[0]
        known = next(e.event_id for e in data.events if e.amount is not None)
        review = facts.validate(data, [
            {"fact_type": "event_amount", "source_ids": [data.images[0]["image_id"]],
             "category": None, "event_ids": [blank, known], "amount": 1234.5,
             "effective_date": None, "period_days": None, "scope": "single_event",
             "certainty": "confirmed", "rationale": "", "unresolved_questions": []}])
        before = data.event(known).amount
        facts.apply_event_facts(data, review)
        self.assertEqual(data.event(blank).amount, Decimal("1234.50"))
        self.assertEqual(data.event(known).amount, before)


class DecisionContractTests(unittest.TestCase):
    def test_every_sample_request_produces_a_contract_valid_row(self):
        for request_id in ("request_0{}".format(n) for n in range(1, 10)):
            with self.subTest(request_id):
                data = bundle(request_id)
                decision = decide.decide(data, recurrence.detect(data, POLICY))
                row = decision.row(explain.template(decision, data))
                self.assertEqual(output.validate_row(row, data), [])

    def test_affordable_now_implies_earliest_date_equals_request_date(self):
        for request_id in ("request_01", "request_09", "request_16"):
            data = bundle(request_id)
            decision = decide.decide(data, recurrence.detect(data, POLICY))
            if decision.affordability_status == "affordable_now":
                self.assertEqual(decision.earliest_date_for_full_payment, data.as_of)

    def test_capacity_fields_ignore_optional_spending_changes(self):
        data = bundle("request_21")
        decision = decide.decide(data, recurrence.detect(data, POLICY))
        baseline = forecast.build(data, recurrence.detect(data, POLICY))
        self.assertEqual(decision.amount_safe_to_pay,
                         baseline.safe_amount_today(data.requested_amount))

    def test_validator_catches_a_broken_partial_plan(self):
        data = bundle("request_19")
        row = {"request_id": "request_19", "amount_safe_to_pay": "1",
               "affordability_status": "affordable_with_plan",
               "recommended_payment_method": "partial_payment",
               "payment_plan": "2024-09-04:1|2024-09-15:2",
               "earliest_date_for_full_payment": "2024-09-15",
               "spending_changes_needed": "none", "decision_explanation": "x"}
        self.assertIn("partial_payments_do_not_sum_to_requested_amount",
                      output.validate_row(row, data))

    def test_validator_catches_an_invented_installment_schedule(self):
        data = bundle("request_02")
        row = {"request_id": "request_02", "amount_safe_to_pay": "0",
               "affordability_status": "affordable_with_plan",
               "recommended_payment_method": "installments",
               "payment_plan": "2025-08-08:1|2025-09-08:1",
               "earliest_date_for_full_payment": "", "spending_changes_needed": "none",
               "decision_explanation": "x"}
        self.assertIn("installment_plan_does_not_match_a_supplied_option",
                      output.validate_row(row, data))

    def test_validator_rejects_a_protected_category_cut(self):
        data = bundle("request_01")
        protected = next(e for e in data.events
                         if e.category in data.protected_categories)
        row = {"request_id": "request_01", "amount_safe_to_pay": "0",
               "affordability_status": "not_affordable",
               "recommended_payment_method": "not_recommended", "payment_plan": "none",
               "earliest_date_for_full_payment": "",
               "spending_changes_needed": "stop:" + protected.event_id,
               "decision_explanation": "x"}
        self.assertIn("spending_change_targets_a_protected_category",
                      output.validate_row(row, data))


class ExplanationTests(unittest.TestCase):
    def test_full_payment_explanation_matches_the_house_style(self):
        data = bundle("request_01")
        decision = decide.decide(data, recurrence.detect(data, POLICY))
        text = explain.template(decision, data)
        self.assertTrue(text.startswith("Pay ZAR 25,256 today."), text)
        self.assertIn("ZAR 18,000", text)

    def test_every_method_produces_a_non_empty_explanation(self):
        data = bundle("request_01")
        decision = decide.decide(data, recurrence.detect(data, POLICY))
        for method in ("full_payment", "installments", "partial_payment", "wait",
                       "not_recommended"):
            clone = decide.Decision(**{**decision.__dict__,
                                       "recommended_payment_method": method,
                                       "payments": ((data.as_of, Decimal("10")),
                                                    (data.as_of + timedelta(days=30),
                                                     Decimal("20")))})
            self.assertTrue(explain.template(clone, data).strip())


if __name__ == "__main__":
    unittest.main()
