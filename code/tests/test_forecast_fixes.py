"""Regression tests for the forecast defects found by sample-calibration analysis.

Each class here pins one defect that made the harness disagree with the supplied
sample answers. The named requests are the cases that exposed them.
"""

import unittest
from datetime import date, timedelta
from decimal import Decimal

from harness import decide, facts, forecast, plans, recurrence
from harness.config import DEFAULT_DATASET, RecurrencePolicy
from harness.ledger import EvidenceLoader

LOADER = EvidenceLoader(DEFAULT_DATASET, include_samples=True)
POLICY = RecurrencePolicy()


def bundle(request_id):
    return LOADER.bundle(request_id)


class CadenceRecoveryTests(unittest.TestCase):
    """A gap in the history must not destroy the pattern around it."""

    def test_monthly_cadence_survives_two_months_of_leave(self):
        # Payroll on the 15th interrupted by leave gives gaps [31, 91]; the
        # median of 61 is a cadence the user never had, and one that would fall
        # outside the recurring range and delete the salary entirely.
        self.assertEqual(recurrence._period_from([31, 91]), 31)
        self.assertEqual(recurrence._period_from([31, 90]), 31)

    def test_unrelated_gaps_fall_back_to_the_median(self):
        self.assertEqual(recurrence._period_from([7, 7, 10, 7]), 7)
        self.assertEqual(recurrence._period_from([3, 30]), 16)

    def test_payroll_interrupted_by_leave_is_still_projected(self):
        data = bundle("request_14")
        payroll = [s for s in recurrence.detect(data, POLICY)
                   if s.direction == "credit" and s.stream == "payroll"]
        self.assertTrue(payroll, "user_14 has payroll before and after leave")
        self.assertTrue(payroll[0].active)
        self.assertLessEqual(payroll[0].period_days, POLICY.max_period_days)


class RequestDateObligationTests(unittest.TestCase):
    """An obligation due today is due; one already settled today is not."""

    def test_occurrence_on_the_request_date_is_projected(self):
        data = bundle("request_19")          # rent last paid 4 Aug, request 4 Sep
        rent = next(s for s in recurrence.detect(data, POLICY) if s.category == "rent")
        self.assertIn(data.as_of, rent.projected_dates(data.as_of, data.horizon_end))

    def test_projection_never_precedes_the_last_recorded_occurrence(self):
        data = bundle("request_19")
        for series in recurrence.detect(data, POLICY):
            for when in series.projected_dates(data.as_of, data.horizon_end):
                self.assertGreater(when, series.last_date)


class ScheduledRowTests(unittest.TestCase):
    """A one-off future commitment is a flow, not a pattern."""

    def test_one_off_scheduled_debit_does_not_join_its_category_pattern(self):
        data = bundle("request_16")          # scheduled "Outstanding rent balance"
        arrears = data.event("event_1442")
        self.assertEqual(arrears.status, "scheduled")
        rent = next(s for s in recurrence.detect(data, POLICY) if s.category == "rent")
        self.assertNotIn(arrears.event_id, rent.supporting_event_ids)
        self.assertLess(rent.last_date, data.as_of)

    def test_confirmed_future_salary_does_extend_the_payroll_pattern(self):
        data = bundle("request_01")          # "Next confirmed salary", scheduled
        payroll = [s for s in recurrence.detect(data, POLICY)
                   if s.direction == "credit" and s.stream == "payroll"]
        self.assertTrue(payroll)
        self.assertGreater(payroll[0].last_date, data.as_of)


class CompletionWindowTests(unittest.TestCase):
    """Plan safety is judged over the window the request is live in."""

    def setUp(self):
        self.bundle = bundle("request_13")
        self.forecast = forecast.build(self.bundle,
                                       recurrence.detect(self.bundle, POLICY), POLICY)

    def test_window_runs_to_the_later_of_deadline_and_payment(self):
        later = self.bundle.deadline + timedelta(days=10)
        self.assertEqual(self.forecast.completion_window(self.bundle.deadline),
                         self.bundle.deadline)
        self.assertEqual(self.forecast.completion_window(self.bundle.deadline, later),
                         later)

    def test_no_deadline_means_the_whole_horizon(self):
        self.assertEqual(self.forecast.completion_window(None), self.forecast.end)

    def test_window_never_runs_past_the_horizon(self):
        far = self.forecast.end + timedelta(days=60)
        self.assertEqual(self.forecast.completion_window(far), self.forecast.end)

    def test_completion_window_finds_a_date_the_full_horizon_rejects(self):
        amount = self.bundle.requested_amount
        self.assertIsNone(self.forecast.earliest_full_payment_date(amount))
        self.assertEqual(
            self.forecast.earliest_full_payment_date(amount,
                                                     deadline=self.bundle.deadline),
            date(2024, 5, 15))

    def test_amount_safe_to_pay_stays_a_ninety_day_measure(self):
        decision = decide.decide(self.bundle, recurrence.detect(self.bundle, POLICY),
                                 policy=POLICY)
        self.assertEqual(decision.amount_safe_to_pay,
                         self.forecast.safe_amount_today(self.bundle.requested_amount))


class NewIncomeFactTests(unittest.TestCase):
    """Confirmed income the history is too short to establish on its own."""

    def setUp(self):
        self.bundle = bundle("request_06")
        self.source = self.bundle.messages[0]["message_id"]

    def claim(self, **overrides):
        raw = {"fact_type": "new_recurring_income", "source_ids": [self.source],
               "category": "salary", "event_ids": [], "amount": 2000,
               "effective_date": (self.bundle.as_of + timedelta(days=10)).isoformat(),
               "period_days": 30, "scope": "ongoing", "certainty": "confirmed",
               "rationale": "", "unresolved_questions": []}
        raw.update(overrides)
        return facts.validate(self.bundle, [raw])

    def test_unconfirmed_new_income_is_refused(self):
        self.assertEqual(self.claim(certainty="likely").rejected[0][1],
                         "cash_increasing_claim_is_not_confirmed")

    def test_new_income_without_a_start_date_is_refused(self):
        self.assertEqual(self.claim(effective_date=None).rejected[0][1],
                         "new_recurring_income_requires_amount_and_start_date")

    def test_new_income_amends_an_existing_stream_rather_than_stacking(self):
        series = recurrence.detect(self.bundle, POLICY)
        before = len([s for s in series if s.direction == "credit"])
        applied = facts.apply_series_facts(self.bundle, series, self.claim())
        self.assertEqual(len([s for s in applied if s.direction == "credit"]), before)
        amended = [s for s in applied if s.direction == "credit" and s.active]
        self.assertTrue(amended)
        self.assertTrue(all(s.amount_override == Decimal("2000") for s in amended))

    def test_new_income_is_added_when_no_stream_is_detected(self):
        data = bundle("request_14")
        series = [s for s in recurrence.detect(data, POLICY) if s.direction == "debit"]
        start = data.as_of + timedelta(days=11)
        review = facts.validate(data, [{
            "fact_type": "new_recurring_income",
            "source_ids": [data.messages[0]["message_id"]],
            "category": "salary", "event_ids": [], "amount": 2717,
            "effective_date": start.isoformat(), "period_days": 30, "scope": "ongoing",
            "certainty": "confirmed", "rationale": "", "unresolved_questions": []}])
        applied = facts.apply_series_facts(data, series, review)
        added = [s for s in applied if s.direction == "credit"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].amount, Decimal("2717"))
        self.assertIn(start, added[0].projected_dates(data.as_of, data.horizon_end))


class ChangeRankingTests(unittest.TestCase):
    """Completing on time outranks avoiding a cut."""

    def test_an_on_time_cut_beats_a_late_clean_plan(self):
        late_clean = plans.Candidate("wait", ((date(2026, 6, 1), Decimal("100")),),
                                     Decimal("100"), on_time=False)
        on_time_cut = plans.Candidate("full_payment",
                                      ((date(2026, 1, 1), Decimal("100")),),
                                      Decimal("100"), changes=("cut",))
        self.assertLess(on_time_cut.rank_key(), late_clean.rank_key())
        self.assertIs(plans.best([late_clean, on_time_cut]), on_time_cut)

    def test_an_on_time_clean_plan_still_beats_an_on_time_cut(self):
        clean = plans.Candidate("installments", ((date(2026, 1, 1), Decimal("200")),),
                                Decimal("200"), "payment_option_09")
        cut = plans.Candidate("full_payment", ((date(2026, 1, 1), Decimal("100")),),
                              Decimal("100"), changes=("cut",))
        self.assertLess(clean.rank_key(), cut.rank_key())
        self.assertIs(plans.best([cut, clean]), clean)


if __name__ == "__main__":
    unittest.main()
