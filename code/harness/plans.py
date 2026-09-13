"""Candidate payment plans and the strict ordering the challenge specifies.

Generation, safety testing and ranking are all deterministic: given the same
validated facts and forecast, the same plan wins every time. The model never
chooses amounts, dates or methods here.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .money import ZERO, parse, quantize

STATUS_NOW = "affordable_now"
STATUS_PLAN = "affordable_with_plan"
STATUS_LATER = "affordable_later"
STATUS_NONE = "not_affordable"

METHOD_FULL = "full_payment"
METHOD_PARTIAL = "partial_payment"
METHOD_INSTALLMENTS = "installments"
METHOD_WAIT = "wait"
METHOD_NONE = "not_recommended"


@dataclass(frozen=True)
class Candidate:
    """One complete, safety-tested way to satisfy the request."""

    method: str
    payments: tuple
    total_cost: Decimal
    option_id: str = ""
    changes: tuple = ()
    on_time: bool = True
    note: str = ""

    @property
    def start(self):
        return self.payments[0][0]

    @property
    def finish(self):
        return self.payments[-1][0]

    @property
    def status(self):
        if self.method == METHOD_WAIT:
            return STATUS_LATER
        if self.method == METHOD_FULL and not self.changes:
            return STATUS_NOW
        return STATUS_PLAN

    def rank_key(self):
        """Strict challenge ordering; earlier criteria dominate completely."""
        return (0 if self.on_time else 1,
                1 if self.changes else 0,
                self.total_cost,
                self.start,
                len(self.payments),
                _option_sort_key(self.option_id))


def _option_sort_key(option_id):
    digits = "".join(ch for ch in option_id if ch.isdigit())
    return (0, int(digits)) if digits else (1, 0)


@dataclass
class OptionReview:
    """Why a supplied offer is or is not usable, kept for the explanation."""

    option_id: str
    method: str
    payments: tuple
    total_cost: Decimal
    reasons: tuple = ()

    @property
    def eligible(self):
        return not self.reasons


def schedule_for(option, request_date):
    """Dates come from the supplied day interval, never an assumed calendar month."""
    from datetime import timedelta
    count = int(option["number_of_payments"])
    step = int(option["payment_frequency_days"] or 0)
    first = date.fromisoformat(option["first_payment_date"])
    amount = quantize(parse(option["payment_amount"]))
    return tuple((first + timedelta(days=index * step), amount) for index in range(count))


def review_options(bundle):
    """Static eligibility of every supplied offer, before any cash-flow test."""
    reviews = []
    for option in sorted(bundle.options, key=lambda o: _option_sort_key(o["payment_option_id"])):
        method = option["payment_method"]
        payments = schedule_for(option, bundle.as_of)
        total = quantize(parse(option["total_payable_amount"]))
        reasons = []
        if method not in bundle.accepted_methods:
            reasons.append("payment_method_not_accepted")
        if method == METHOD_INSTALLMENTS:
            limit = bundle.max_installment_months
            if limit is None:
                reasons.append("user_does_not_consider_installments")
            elif len(payments) > limit:
                reasons.append("exceeds_max_installment_months")
        if payments[0][0] < bundle.as_of:
            reasons.append("starts_before_request_date")
        if payments[-1][0] > bundle.deadline:
            reasons.append("finishes_after_desired_completion_date")
        declared = quantize(parse(option["payment_amount"])) * len(payments)
        if declared != total:
            reasons.append("schedule_total_does_not_match_total_payable")
        reviews.append(OptionReview(option["payment_option_id"], method, payments,
                                    total, tuple(reasons)))
    return reviews


def generate(bundle, forecast, earliest_full, *, changes=(), deadline=None):
    """Every eligible plan that is safe against this forecast and its deadline."""
    candidates = []
    requested = bundle.requested_amount
    changes = tuple(changes)

    if METHOD_FULL in bundle.accepted_methods and bundle.as_of <= bundle.deadline:
        payments = ((bundle.as_of, requested),)
        if forecast.supports_payments(payments, deadline=deadline):
            candidates.append(Candidate(METHOD_FULL, payments, requested, changes=changes))

    for review in review_options(bundle):
        if review.method != METHOD_INSTALLMENTS or not review.eligible:
            continue
        if forecast.supports_payments(review.payments, deadline=deadline):
            candidates.append(Candidate(METHOD_INSTALLMENTS, review.payments,
                                        review.total_cost, review.option_id, changes))

    safe_today = forecast.safe_amount_today(requested)
    if (bundle.allows_partial and METHOD_PARTIAL in bundle.accepted_methods
            and ZERO < safe_today < requested and earliest_full is not None
            and earliest_full <= bundle.deadline and earliest_full > bundle.as_of):
        payments = ((bundle.as_of, safe_today), (earliest_full, requested - safe_today))
        if forecast.supports_payments(payments, deadline=deadline):
            candidates.append(Candidate(METHOD_PARTIAL, payments, requested, changes=changes))

    # ``wait`` is eligible whenever full payment becomes safe later and the user
    # accepts full_payment; the contract attaches no deadline test to that
    # eligibility, so a late date still reports capacity and ranks last.
    if (METHOD_FULL in bundle.accepted_methods and earliest_full is not None
            and earliest_full > bundle.as_of):
        payments = ((earliest_full, requested),)
        if forecast.supports_payments(payments, deadline=deadline):
            candidates.append(Candidate(METHOD_WAIT, payments, requested, changes=changes,
                                        on_time=earliest_full <= bundle.deadline))

    return candidates


def best(candidates):
    return min(candidates, key=Candidate.rank_key) if candidates else None


def no_plan(bundle):
    """The fallback when no eligible plan is both safe and on time."""
    return Candidate(METHOD_NONE, (), ZERO)
