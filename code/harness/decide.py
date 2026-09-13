"""The locked decision: forecast, candidates, changes and the final output row.

Everything in this module is deterministic. The model's only inputs are the
already-validated interpretation facts that shaped the series list; its only
later job is wording the explanation of fields decided here.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import changes as change_search
from . import forecast as forecasting
from . import plans
from .money import ZERO, normalized, plan_amount


@dataclass
class Decision:
    """Locked computed fields plus the evidence trail behind them."""

    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payments: tuple
    earliest_date_for_full_payment: date | None
    spending_changes: tuple
    currency: str
    minimum_balance: Decimal
    projected_minimum: Decimal
    requested_amount: Decimal
    deadline: date
    as_of: date
    option_id: str = ""
    total_cost: Decimal = ZERO
    rejected_options: tuple = ()
    fact_summaries: tuple = ()
    coverage: dict = field(default_factory=dict)

    def payment_plan(self):
        if not self.payments:
            return "none"
        return "|".join("{}:{}".format(when.isoformat(), plan_amount(amount))
                        for when, amount in self.payments)

    def spending_changes_needed(self):
        return change_search.render_all(self.spending_changes)

    def row(self, explanation):
        return {
            "request_id": self.request_id,
            "amount_safe_to_pay": normalized(self.amount_safe_to_pay),
            "affordability_status": self.affordability_status,
            "recommended_payment_method": self.recommended_payment_method,
            "payment_plan": self.payment_plan(),
            "earliest_date_for_full_payment": (
                self.earliest_date_for_full_payment.isoformat()
                if self.earliest_date_for_full_payment else ""),
            "spending_changes_needed": self.spending_changes_needed(),
            "decision_explanation": explanation,
        }


def decide(bundle, series_list, *, fact_summaries=(), coverage=None):
    """Run the full deterministic decision for one request."""
    baseline = forecasting.build(bundle, series_list)
    safe_today = baseline.safe_amount_today(bundle.requested_amount)
    earliest_full = baseline.earliest_full_payment_date(bundle.requested_amount)

    candidate = plans.best(plans.generate(bundle, baseline, earliest_full))
    applied = ()
    if candidate is None:
        def builder(selection):
            adjusted = forecasting.apply_changes(bundle, series_list, selection)
            # Capacity fields stay on the unchanged budget; only the plan changes.
            return plans.best(plans.generate(
                bundle, adjusted,
                adjusted.earliest_full_payment_date(bundle.requested_amount),
                changes=selection))
        candidate, applied = change_search.search(bundle, series_list, builder)

    if candidate is None:
        candidate = plans.no_plan(bundle)
        status, method = plans.STATUS_NONE, plans.METHOD_NONE
    else:
        status, method = candidate.status, candidate.method

    final = baseline if not applied else forecasting.apply_changes(bundle, series_list, applied)
    projected_minimum = final.with_flows(
        forecasting.Flow(when, -amount, "payment", "recommended_payment")
        for when, amount in candidate.payments).minimum_balance()

    rejected = tuple(review for review in plans.review_options(bundle) if not review.eligible)
    return Decision(
        request_id=bundle.request["request_id"],
        amount_safe_to_pay=safe_today,
        affordability_status=status,
        recommended_payment_method=method,
        payments=candidate.payments,
        earliest_date_for_full_payment=earliest_full,
        spending_changes=applied,
        currency=bundle.home_currency,
        minimum_balance=bundle.minimum_balance,
        projected_minimum=projected_minimum,
        requested_amount=bundle.requested_amount,
        deadline=bundle.deadline,
        as_of=bundle.as_of,
        option_id=candidate.option_id,
        total_cost=candidate.total_cost,
        rejected_options=rejected,
        fact_summaries=tuple(fact_summaries),
        coverage=coverage or {})
