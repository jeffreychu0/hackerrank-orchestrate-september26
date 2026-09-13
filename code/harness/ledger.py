"""Mandatory evidence bundle: everything a decision may legitimately rest on.

Code owns retrieval so a missed obligation can never be blamed on the model
skipping a tool call. Nothing here interprets meaning; it normalises rows into
dated home-currency cash effects and records why a row was kept or excluded.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from tools.dataset import DatasetStore

from .money import MoneyError, parse, quantize

#: Statuses whose cash never moves, per the 90-day safety check.
NON_CASH_STATUSES = frozenset({"cancelled", "failed", "unrealized"})
FUTURE_STATUSES = frozenset({"pending", "scheduled"})


class EvidenceError(ValueError):
    """The evidence bundle could not be assembled for a request."""


def iso(value):
    return date.fromisoformat(value)


@dataclass(frozen=True)
class CashEvent:
    """One financial-event row reduced to its cash effect, with provenance."""

    event_id: str
    event_type: str
    description: str
    category: str
    direction: str
    status: str
    amount: Decimal | None
    currency: str
    event_date: date
    settlement_date: date | None
    flexibility: str
    minimum_allowed_amount: Decimal | None
    linked_event_id: str
    home_amount: Decimal | None = None
    exclusion_reason: str = ""

    @property
    def signed(self):
        """Home-currency signed cash effect, or None when still unknown."""
        if self.home_amount is None:
            return None
        return self.home_amount if self.direction == "credit" else -self.home_amount

    @property
    def cash_date(self):
        return self.settlement_date or self.event_date


@dataclass
class EvidenceBundle:
    """Per-request coverage record. Every field is loaded, never model-requested."""

    request: dict
    profile: dict
    user_id: str
    home_currency: str
    as_of: date
    horizon_end: date
    deadline: date
    requested_amount: Decimal
    allows_partial: bool
    opening_balance: Decimal
    minimum_balance: Decimal
    events: list
    messages: list
    images: list
    options: list
    accepted_methods: frozenset
    protected_categories: frozenset
    reducible_categories: frozenset
    stoppable_categories: frozenset
    max_installment_months: int | None
    unknown_amount_event_ids: tuple = ()
    unconverted_event_ids: tuple = ()
    notes: list = field(default_factory=list)

    @property
    def history(self):
        return [e for e in self.events if e.status == "settled" and e.cash_date <= self.as_of]

    @property
    def future_records(self):
        return [e for e in self.events
                if e.status in FUTURE_STATUSES and e.cash_date and e.cash_date > self.as_of]

    def event(self, event_id):
        for candidate in self.events:
            if candidate.event_id == event_id:
                return candidate
        return None


def _pipe_set(value):
    return frozenset(part for part in (value or "").split("|") if part)


def _exclusion_reason(row):
    if row["status"] == "cancelled":
        return "cancelled_transaction"
    if row["status"] == "failed":
        return "failed_transaction"
    if row["status"] == "unrealized":
        return "unrealized_valuation"
    if row["direction"] == "non_cash":
        return "non_cash_record"
    if row["status"] == "pending" and row["direction"] == "credit":
        return "pending_credit_not_yet_cash"
    return ""


class EvidenceLoader:
    """Loads the dataset once and produces one bundle per request."""

    def __init__(self, dataset_root, *, include_samples=False, forecast_days=90):
        self.store = DatasetStore(dataset_root, include_samples=include_samples)
        self.forecast_days = forecast_days

    @property
    def request_ids(self):
        return list(self.store.requests)

    def convert(self, amount, currency, target, on_date):
        """Exact dated directional FX. No inverse rates, no live lookups."""
        if amount is None:
            return None
        if currency == target:
            return amount
        row = self.store.rates.get((on_date.isoformat(), currency, target))
        if row is None:
            return None
        return quantize(amount * parse(row["rate"]))

    def bundle(self, request_id):
        request = self.store.requests.get(request_id)
        if request is None:
            raise EvidenceError("Unknown request_id: " + str(request_id))
        profile = self.store.profiles.get(request["user_id"])
        if profile is None:
            raise EvidenceError("No profile for " + request["user_id"])
        as_of = iso(request["request_date"])
        currency = profile["home_currency"]
        events, unknown, unconverted = [], [], []
        for row in self.store.events_by_user[request["user_id"]]:
            event = self._cash_event(row, currency)
            events.append(event)
            if event.amount is None:
                unknown.append(event.event_id)
            elif event.home_amount is None and event.status not in NON_CASH_STATUSES:
                unconverted.append(event.event_id)
        events.sort(key=lambda e: (e.cash_date, e.event_id))
        messages = sorted(
            (row for row in self.store.messages
             if row["user_id"] == request["user_id"]
             and row["request_id"] in ("", request_id)
             and row["sent_at"][:10] <= request["request_date"]),
            key=lambda r: (r["sent_at"], r["message_id"]))
        images = [row for row in self.store.images.values()
                  if row["user_id"] == request["user_id"]
                  and row["request_id"] in ("", request_id)]
        options = [row for row in self.store.options if row["request_id"] == request_id]
        installment_limit = profile["max_installment_months"].strip()
        return EvidenceBundle(
            request=request, profile=profile, user_id=request["user_id"],
            home_currency=currency, as_of=as_of,
            horizon_end=as_of + timedelta(days=self.forecast_days),
            deadline=iso(request["desired_completion_date"]),
            requested_amount=parse(request["requested_amount"]),
            allows_partial=request["allows_partial_payment"].strip().lower() == "true",
            opening_balance=parse(profile["current_available_balance"]),
            minimum_balance=parse(profile["minimum_balance_to_keep"]),
            events=events, messages=messages, images=images, options=options,
            accepted_methods=_pipe_set(profile["payment_methods_user_will_consider"]),
            protected_categories=_pipe_set(profile["expense_categories_to_protect"]),
            reducible_categories=_pipe_set(profile["expense_categories_user_is_willing_to_reduce"]),
            stoppable_categories=_pipe_set(profile["expense_categories_user_is_willing_to_stop"]),
            max_installment_months=int(installment_limit) if installment_limit else None,
            unknown_amount_event_ids=tuple(unknown),
            unconverted_event_ids=tuple(unconverted))

    def _cash_event(self, row, currency):
        try:
            amount = parse(row["amount"])
            minimum = parse(row["minimum_allowed_amount"])
        except MoneyError as exc:
            raise EvidenceError(row["event_id"] + ": " + str(exc)) from None
        settlement = row["settlement_date"].strip()
        event_date = iso(row["event_date"])
        settlement_date = iso(settlement) if settlement else None
        home = None
        if amount is not None and row["direction"] != "non_cash":
            home = self.convert(amount, row["currency"], currency,
                                settlement_date or event_date)
        return CashEvent(
            event_id=row["event_id"], event_type=row["event_type"],
            description=row["description"], category=row["category"],
            direction=row["direction"], status=row["status"], amount=amount,
            currency=row["currency"], event_date=event_date,
            settlement_date=settlement_date, flexibility=row["flexibility"],
            minimum_allowed_amount=minimum, linked_event_id=row["linked_event_id"],
            home_amount=home, exclusion_reason=_exclusion_reason(row))
