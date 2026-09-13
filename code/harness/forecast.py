"""Deterministic 90-day cash-flow forecast and the safety tests built on it.

Every payment in every candidate plan is tested against the same balance path,
so a plan can never be accepted because a first installment happened to be
small. The forecast is a pure function of the bundle, the detected series and
the validated interpretation facts.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .money import ZERO, clamp, quantize
from .recurrence import Series


@dataclass(frozen=True)
class Flow:
    """One dated cash movement in the projection, with why it is there."""

    when: date
    amount: Decimal          # signed: credits positive, debits negative
    origin: str              # "opening" | "record" | "projection" | "change" | "payment"
    label: str
    source_id: str = ""


@dataclass
class Forecast:
    """A dated balance path plus the safety questions the contract asks of it."""

    opening: Decimal
    minimum: Decimal
    start: date
    end: date
    flows: list = field(default_factory=list)

    def with_flows(self, extra):
        return Forecast(self.opening, self.minimum, self.start, self.end,
                        list(self.flows) + list(extra))

    @staticmethod
    def _order(flow):
        # Same-day money in lands before money out: a salary credited on payday
        # funds that day's obligations, which is how the supplied samples read.
        return (flow.when, 0 if flow.amount > ZERO else 1, flow.label, flow.source_id)

    def path(self):
        """Running balance at each dated step, in chronological order."""
        running = self.opening
        points = [(self.start, running)]
        for flow in sorted(self.flows, key=self._order):
            if flow.when < self.start or flow.when > self.end:
                continue
            running += flow.amount
            points.append((flow.when, running))
        return points

    def minimum_balance(self, *, on_or_after=None):
        """Lowest projected balance from ``on_or_after`` to the horizon end."""
        floor = None
        for when, balance in self.path():
            if on_or_after is not None and when < on_or_after:
                continue
            floor = balance if floor is None else min(floor, balance)
        if floor is None:
            floor = self.opening
        return floor

    def balance_on(self, when):
        balance = self.opening
        for point_date, value in self.path():
            if point_date <= when:
                balance = value
        return balance

    def headroom(self, *, on_or_after=None):
        return self.minimum_balance(on_or_after=on_or_after) - self.minimum

    def is_safe(self):
        return self.headroom() >= ZERO

    def safe_amount_today(self, cap):
        """Largest amount payable on the start date that never breaks the floor."""
        return clamp(quantize(self.headroom()), ZERO, cap)

    def supports_payments(self, payments):
        """True when every dated payment keeps the whole path above the floor."""
        trial = self.with_flows(
            Flow(when, -amount, "payment", "recommended_payment") for when, amount in payments)
        return trial.is_safe()

    def earliest_full_payment_date(self, amount):
        """First date a single full payment is safe, or None inside the horizon.

        Capacity only, exactly as the contract defines it: independent of which
        methods the user accepts and of any optional spending change.
        """
        if amount <= ZERO:
            return self.start
        candidates = {self.start}
        for flow in self.flows:
            if self.start <= flow.when <= self.end:
                candidates.add(flow.when)
                if flow.when + timedelta(days=1) <= self.end:
                    candidates.add(flow.when + timedelta(days=1))
        for when in sorted(candidates):
            if self.supports_payments([(when, amount)]):
                return when
        return None


def _record_flows(bundle):
    """Confirmed future rows: reserve pending debits, ignore pending credits."""
    flows = []
    for event in bundle.events:
        if event.exclusion_reason or event.home_amount is None:
            continue
        cash_date = event.cash_date
        if cash_date is None or not (bundle.as_of < cash_date <= bundle.horizon_end):
            continue
        if event.status not in ("pending", "scheduled"):
            continue
        flows.append(Flow(cash_date, event.signed, "record",
                          "{}:{}".format(event.status, event.category), event.event_id))
    return flows


def _projection_flows(bundle, series_list):
    """Recurring series projected forward, minus dates a confirmed row covers."""
    covered = {}
    for event in bundle.events:
        if event.status in ("pending", "scheduled") and event.cash_date and \
                event.cash_date > bundle.as_of and not event.exclusion_reason:
            covered.setdefault((event.event_type, event.category, event.direction), []) \
                .append(event.cash_date)
    flows = []
    window = 3
    for series in series_list:
        if not series.active:
            continue
        occurrences = series.projected_dates(bundle.as_of, bundle.horizon_end)
        single = series.override_scope == "next_occurrence"
        for index, when in enumerate(occurrences):
            # An amendment scoped to the next payment amends only that payment;
            # later occurrences fall back to the pattern the history supports.
            amount = series.amount if (single and index) else series.effective_amount
            if series.date_override is not None and (index == 0 or not single):
                when = series.date_override if index == 0 else when
            if any(abs((when - taken).days) <= window for taken in covered.get(series.key, ())):
                continue
            if amount == ZERO:
                continue
            signed = amount if series.direction == "credit" else -amount
            flows.append(Flow(when, signed, "projection", series.label(),
                              series.last_event_id))
    return flows


def build(bundle, series_list):
    """The baseline forecast: no request payment, no optional spending change."""
    forecast = Forecast(opening=bundle.opening_balance, minimum=bundle.minimum_balance,
                        start=bundle.as_of, end=bundle.horizon_end)
    return forecast.with_flows(_record_flows(bundle) + _projection_flows(bundle, series_list))


def apply_changes(bundle, series_list, changes):
    """Rebuild the forecast with a set of permitted spending changes applied."""
    adjusted = []
    by_event = {change.event_id: change for change in changes}
    for series in series_list:
        change = by_event.get(series.last_event_id)
        if change is None:
            adjusted.append(series)
            continue
        if change.action == "stop":
            clone = _clone(series, active=False, suppressed_reason="stopped_by_recommendation")
        else:
            clone = _clone(series, amount_override=change.new_amount)
        adjusted.append(clone)
    return build(bundle, adjusted)


def _clone(series: Series, **updates):
    values = series.__dict__.copy()
    values.update(updates)
    return Series(**values)
