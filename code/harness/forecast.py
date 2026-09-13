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

    def is_safe(self, *, until=None):
        """Does the balance hold the floor through ``until`` (default: the horizon)?"""
        limit = self.end if until is None else min(until, self.end)
        return all(balance >= self.minimum for when, balance in self.path() if when <= limit)

    def safe_amount_today(self, cap):
        """Largest amount payable on the start date that never breaks the floor."""
        return clamp(quantize(self.headroom()), ZERO, cap)

    def completion_window(self, deadline, last_payment=None):
        """How far a payment has to keep the balance safe.

        The request is live from the request date until it is completed, so the
        window runs to the later of its completion deadline and the payment
        itself. With no deadline supplied this is simply the whole horizon.
        """
        if deadline is None:
            return self.end
        end = deadline if last_payment is None else max(deadline, last_payment)
        return min(end, self.end)

    def supports_payments(self, payments, *, deadline=None):
        """True when every dated payment holds the floor across its window."""
        trial = self.with_flows(
            Flow(when, -amount, "payment", "recommended_payment") for when, amount in payments)
        return trial.is_safe(until=self.completion_window(deadline, payments[-1][0]))

    def candidate_dates(self):
        """Dates worth testing: the forecast only steps where a flow lands."""
        dates = {self.start}
        for flow in self.flows:
            if self.start <= flow.when <= self.end:
                dates.add(flow.when)
                if flow.when + timedelta(days=1) <= self.end:
                    dates.add(flow.when + timedelta(days=1))
        return sorted(dates)

    def earliest_full_payment_date(self, amount, *, deadline=None):
        """First date a single full payment is safe, or None inside the horizon.

        Capacity only, exactly as the contract defines it: independent of which
        methods the user accepts and of any optional spending change.
        """
        if amount <= ZERO:
            return self.start
        for when in self.candidate_dates():
            if self.supports_payments([(when, amount)], deadline=deadline):
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


def _projection_flows(bundle, series_list, policy=None):
    """Recurring series projected forward, minus dates a confirmed row covers."""
    from .config import RecurrencePolicy
    policy = policy or RecurrencePolicy()
    covered = {}
    for event in bundle.events:
        if event.status in ("pending", "scheduled") and event.cash_date and \
                event.cash_date > bundle.as_of and not event.exclusion_reason:
            covered.setdefault((event.event_type, event.category, event.direction), []) \
                .append(event.cash_date)
    flows = []
    for series in series_list:
        if not series.active:
            continue
        occurrences = series.projected_dates(bundle.as_of, bundle.horizon_end)
        single = series.override_scope == "next_occurrence"
        skip = _suppressed_occurrences(occurrences, sorted(covered.get(series.key, ())),
                                       series.period_days, policy)
        for index, when in enumerate(occurrences):
            # An amendment scoped to the next payment amends only that payment;
            # later occurrences fall back to the pattern the history supports.
            amount = series.amount if (single and index) else series.effective_amount
            if series.date_override is not None and (index == 0 or not single):
                when = series.date_override if index == 0 else when
            if index in skip or amount == ZERO:
                continue
            signed = amount if series.direction == "credit" else -amount
            flows.append(Flow(when, signed, "projection", series.label(),
                              series.last_event_id))
    return flows


def _suppressed_occurrences(occurrences, explicit, period, policy):
    """Which projected occurrences a confirmed row in the same category covers.

    A confirmed row is already in the forecast as its own flow. Whether it also
    replaces the pattern's occurrence for that cycle is a modelling choice: a
    pending fuel authorisation plausibly is that week's transport spend, while a
    scheduled school fee is plainly extra.
    """
    if policy.explicit_row_handling == "add" or not explicit:
        return set()
    skip = set()
    if policy.explicit_row_handling == "substitute":
        for when in explicit:
            nearest, best = None, None
            for index, occurrence in enumerate(occurrences):
                if index in skip:
                    continue
                distance = abs((occurrence - when).days)
                if distance <= period and (best is None or distance < best):
                    nearest, best = index, distance
            if nearest is not None:
                skip.add(nearest)
        return skip
    span = policy.explicit_match_window_days
    for index, occurrence in enumerate(occurrences):
        if any(abs((occurrence - when).days) <= span for when in explicit):
            skip.add(index)
    return skip


def build(bundle, series_list, policy=None):
    """The baseline forecast: no request payment, no optional spending change."""
    forecast = Forecast(opening=bundle.opening_balance, minimum=bundle.minimum_balance,
                        start=bundle.as_of, end=bundle.horizon_end)
    return forecast.with_flows(_record_flows(bundle)
                               + _projection_flows(bundle, series_list, policy))


def apply_changes(bundle, series_list, changes, policy=None):
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
    return build(bundle, adjusted, policy)


def _clone(series: Series, **updates):
    values = series.__dict__.copy()
    values.update(updates)
    return Series(**values)
