"""Recurrence reconstruction: the recurring budget the dataset never supplies.

Code proposes the pattern from settled history plus confirmed future rows; the
model only gets to say when an exception applies (a final payroll, a rent
increase, a lapsed second income). Repetition alone never becomes income here:
a series is projected forward, and interpretation may cancel or amend it.
"""

import calendar
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .config import RecurrencePolicy
from .money import quantize

VARIABLE_ESSENTIAL_CATEGORIES = frozenset({"groceries", "transport", "utilities", "dining"})


def add_months(anchor, months):
    """Calendar-month step clamped to the end of short months."""
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


@dataclass
class Series:
    """A detected recurring cash pattern with the rows that support it."""

    key: tuple
    event_type: str
    category: str
    direction: str
    period_days: int
    monthly: bool
    amount: Decimal
    last_date: date
    last_event_id: str
    descriptions: tuple
    occurrences: int
    supporting_event_ids: tuple
    flexibility: str
    minimum_allowed_amount: Decimal | None
    stream: str = ""
    active: bool = True
    suppressed_reason: str = ""
    amount_override: Decimal | None = None
    date_override: date | None = None
    override_scope: str = ""
    override_sources: tuple = ()
    extra_note: str = ""

    @property
    def effective_amount(self):
        return self.amount if self.amount_override is None else self.amount_override

    @property
    def signed_amount(self):
        amount = self.effective_amount
        return amount if self.direction == "credit" else -amount

    def label(self):
        if self.direction == "credit" and self.stream:
            return "{}/{}".format(self.category, self.stream)
        return "{}/{}".format(self.category, self.direction)

    def projected_dates(self, start_exclusive, end_inclusive):
        """Occurrence dates strictly after ``start_exclusive`` up to the horizon."""
        dates = []
        step = 1
        while True:
            if self.monthly:
                nxt = add_months(self.last_date, step)
            else:
                nxt = self.last_date + timedelta(days=self.period_days * step)
            if nxt > end_inclusive:
                break
            step += 1
            if nxt > start_exclusive:
                dates.append(nxt)
            if step > 400:
                break
        return dates


#: How the dataset words each kind of income. Wording varies month to month, so
#: a stream is recognised by its kind rather than by an exact description.
INCOME_STREAMS = (
    ("payroll", ("payroll", "salary", "wages")),
    ("platform_earnings", ("platform payout", "app earnings", "marketplace payout",
                           "driver ", "delivery platform", "gig ")),
    ("variable_incentive", ("bonus", "commission")),
    ("independent_work", ("freelance", "contract payment", "consulting", "retainer",
                          "invoice payment", "milestone", "project payment",
                          "independent work")),
    ("windfall", ("prize", "lottery", "winning")),
    ("reimbursement", ("reimbursement", "refund", "reversal")),
)


def income_stream(description):
    """Name the income stream a credit belongs to.

    ``Payroll credit``, ``Base salary`` and ``Next confirmed salary`` are one
    employment income across time; a quarterly bonus, gig payouts and freelance
    project fees are separate streams that can stop, change or be excluded on
    their own. Grouping by exact wording instead would fragment a freelancer's
    income into unprojectable singletons.
    """
    text = description.strip().lower()
    for name, markers in INCOME_STREAMS:
        if any(marker in text for marker in markers):
            return name
    return text


def _group_key(event):
    """Debits group by category; credits also split by income stream.

    A grocery budget is one variable essential regardless of which shop it came
    from, so merchant wording must not fragment it.
    """
    if event.direction == "credit":
        return (event.event_type, event.category, event.direction,
                income_stream(event.description))
    return (event.event_type, event.category, event.direction, "")


def _merge_confirmed_future_income(groups, bundle, policy):
    """Fold a lone confirmed future credit into the income stream it continues.

    ``Next confirmed salary`` is one scheduled row with its own wording; on its
    own it can never establish a pattern, but it is the next occurrence of the
    payroll series the history already supports.
    """
    merged = {key: list(events) for key, events in groups.items()}
    for key, events in list(merged.items()):
        if key[2] != "credit" or len(events) >= policy.min_occurrences:
            continue
        if not any(e.status == "scheduled" and e.cash_date > bundle.as_of for e in events):
            continue
        best, best_count = None, 0
        for other, other_events in merged.items():
            if other == key or other[2] != "credit" or other[1] != key[1]:
                continue
            settled = [e for e in other_events if e.status == "settled"]
            if len(settled) > best_count:
                best, best_count = other, len(settled)
        if best is not None and best_count >= policy.min_occurrences:
            merged[best].extend(events)
            del merged[key]
    return merged


def _is_confirmed_income(amounts, dates, bundle, policy):
    """Only steady income may be projected forward.

    A confirmed future row settles it outright. Otherwise payroll proves itself
    by repeating the same figure, while gig and platform earnings that move with
    every payout are not income the user can count on, and the challenge forbids
    inventing unsupported future income.
    """
    if policy.income_stability == "off":
        return True
    if any(when > bundle.as_of for when in dates):
        return True
    window = [a for a in amounts[-policy.income_window:]]
    if len(window) < 2:
        return False
    if policy.income_stability == "repeat":
        return any(window.count(value) >= 2 for value in window)
    average = sum(window) / len(window)
    if average == 0:
        return False
    return float((max(window) - min(window)) / average) <= policy.income_spread_limit


def _estimate(amounts, estimator):
    if estimator == "last":
        return amounts[-1]
    if estimator == "median":
        return Decimal(str(statistics.median([float(a) for a in amounts])))
    if estimator == "mean3":
        window = amounts[-3:]
        return sum(window) / len(window)
    if estimator == "max3":
        return max(amounts[-3:])
    return sum(amounts) / len(amounts)


def detect(bundle, policy: RecurrencePolicy | None = None):
    """Group the bundle's cash rows into recurring series.

    Debits group by (event_type, category) because a category such as groceries
    is one variable essential budget with many merchant descriptions. Credits
    group the same way so that a scheduled ``Next confirmed salary`` row extends
    the payroll series it belongs to instead of starting a rival one.
    """
    policy = policy or RecurrencePolicy()
    groups = {}
    for event in bundle.events:
        if event.direction not in ("debit", "credit"):
            continue
        if event.exclusion_reason or event.home_amount is None:
            continue
        cash_date = event.cash_date
        if cash_date is None:
            continue
        settled_history = event.status == "settled" and cash_date <= bundle.as_of
        confirmed_future = event.status == "scheduled" and cash_date > bundle.as_of
        if not (settled_history or confirmed_future):
            continue
        groups.setdefault(_group_key(event), []).append(event)
    groups = _merge_confirmed_future_income(groups, bundle, policy)

    low, high = policy.monthly_period_range
    series = []
    for full_key, events in groups.items():
        events.sort(key=lambda e: (e.cash_date, e.event_id))
        key = (full_key[0], full_key[1], full_key[2])
        if len(events) < policy.min_occurrences:
            continue
        dates = [e.cash_date for e in events]
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        period = int(statistics.median(gaps))
        if not 1 <= period <= policy.max_period_days:
            continue
        amounts = [e.home_amount for e in events]
        last = events[-1]
        lapsed = (policy.stale_periods
                  and dates[-1] < bundle.as_of - timedelta(days=period * policy.stale_periods)
                  and not any(when > bundle.as_of for when in dates))
        unstable = key[2] == "credit" and not _is_confirmed_income(amounts, dates, bundle, policy)
        series.append(Series(
            key=key, event_type=key[0], category=key[1], direction=key[2],
            period_days=period, monthly=low <= period <= high,
            amount=quantize(_estimate(amounts, policy.credit_estimator
                                      if key[2] == "credit" and policy.credit_estimator
                                      else policy.amount_estimator)),
            last_date=dates[-1], last_event_id=last.event_id,
            descriptions=tuple(dict.fromkeys(e.description for e in events[-4:])),
            occurrences=len(events),
            supporting_event_ids=tuple(e.event_id for e in events[-4:]),
            flexibility=last.flexibility,
            minimum_allowed_amount=last.minimum_allowed_amount,
            stream=full_key[3],
            active=not (lapsed or unstable),
            suppressed_reason=("pattern_lapsed_before_request_date" if lapsed else
                               "variable_income_not_confirmed_recurring" if unstable else "")))

    for item in series:
        if item.direction != "credit":
            continue
        tail = " ".join(item.descriptions).lower()
        if any(marker in tail for marker in policy.terminal_income_markers):
            item.active = False
            item.suppressed_reason = "income_series_marked_final_in_history"
    series.sort(key=lambda s: (s.direction, s.category, s.event_type))
    return series


def latest_occurrence(bundle, series):
    """The most recent settled row of a series: the id a spending change cites."""
    best = None
    for event in bundle.events:
        if (event.event_type, event.category, event.direction) != series.key:
            continue
        if event.status != "settled" or event.cash_date > bundle.as_of:
            continue
        if best is None or (event.cash_date, event.event_id) > (best.cash_date, best.event_id):
            best = event
    return best
