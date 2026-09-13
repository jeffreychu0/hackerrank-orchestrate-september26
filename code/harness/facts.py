"""Proposed facts: the only channel through which interpretation reaches money.

The model returns claims, never ledger edits. Every claim is checked here for a
real source, an owned event, a known category, a sane date and a parseable
amount before it can change a single projected flow. Checks like these cannot
prove the model read a message correctly, so an unresolved claim stays visible
in the decision record instead of quietly becoming income.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from .money import MoneyError, ZERO, parse, quantize
from .recurrence import Series, add_months

#: Claim vocabulary. Anything outside this set is rejected, not guessed at.
FACT_TYPES = (
    "income_stream_ends",
    "income_amount_change",
    "income_date_change",
    "recurring_expense_amount_change",
    "new_recurring_expense",
    "new_recurring_income",
    "exclude_projection",
    "event_amount",
    "exclude_event",
    "no_material_effect",
)

CERTAINTY = ("confirmed", "likely", "unconfirmed")

#: Claims that free up cash need confirmation; claims that reserve cash do not.
CASH_INCREASING = frozenset({"income_amount_change", "event_amount",
                             "new_recurring_income"})


@dataclass(frozen=True)
class ProposedFact:
    fact_type: str
    source_ids: tuple = ()
    category: str = ""
    event_ids: tuple = ()
    amount: Decimal | None = None
    currency: str = ""
    effective_date: date | None = None
    period_days: int | None = None
    scope: str = "ongoing"
    certainty: str = "unconfirmed"
    rationale: str = ""
    unresolved_questions: tuple = ()

    def summary(self):
        parts = [self.fact_type]
        if self.category:
            parts.append(self.category)
        if self.amount is not None:
            parts.append(str(quantize(self.amount)))
        if self.effective_date:
            parts.append(self.effective_date.isoformat())
        if self.source_ids:
            parts.append("from " + ",".join(self.source_ids))
        return " ".join(parts)


@dataclass
class FactReview:
    accepted: tuple = ()
    rejected: tuple = ()      # (raw_fact, reason)
    unresolved: tuple = ()

    def summaries(self):
        return tuple(fact.summary() for fact in self.accepted)


def _as_tuple(value):
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def validate(bundle, raw_facts):
    """Turn model JSON into facts the forecast is allowed to act on."""
    known_sources = {row["message_id"] for row in bundle.messages}
    known_sources |= {row["image_id"] for row in bundle.images}
    owned_events = {event.event_id for event in bundle.events}
    known_categories = {event.category for event in bundle.events}
    earliest = bundle.as_of - timedelta(days=400)
    accepted, rejected, unresolved = [], [], []

    for raw in raw_facts or ():
        if not isinstance(raw, dict):
            rejected.append((raw, "fact_is_not_an_object"))
            continue
        fact_type = str(raw.get("fact_type", "")).strip()
        if fact_type not in FACT_TYPES:
            rejected.append((raw, "unknown_fact_type"))
            continue
        sources = _as_tuple(raw.get("source_ids"))
        if not sources or any(source not in known_sources for source in sources):
            rejected.append((raw, "source_id_not_in_supplied_evidence"))
            continue
        event_ids = _as_tuple(raw.get("event_ids"))
        if any(event_id not in owned_events for event_id in event_ids):
            rejected.append((raw, "event_id_not_owned_by_user"))
            continue
        category = str(raw.get("category") or "").strip()
        if category and category not in known_categories:
            rejected.append((raw, "category_absent_from_user_history"))
            continue
        try:
            amount = parse(raw.get("amount"))
        except MoneyError:
            rejected.append((raw, "amount_is_not_a_finite_decimal"))
            continue
        if amount is not None and amount < ZERO:
            rejected.append((raw, "negative_amount"))
            continue
        effective = raw.get("effective_date") or ""
        try:
            effective_date = date.fromisoformat(effective) if effective else None
        except ValueError:
            rejected.append((raw, "effective_date_is_not_iso_yyyy_mm_dd"))
            continue
        if effective_date and not earliest <= effective_date <= bundle.horizon_end:
            rejected.append((raw, "effective_date_outside_history_and_forecast"))
            continue
        certainty = str(raw.get("certainty") or "unconfirmed").strip()
        if certainty not in CERTAINTY:
            certainty = "unconfirmed"
        if fact_type in CASH_INCREASING and certainty != "confirmed":
            rejected.append((raw, "cash_increasing_claim_is_not_confirmed"))
            continue
        currency = str(raw.get("currency") or "").strip()
        if currency and currency != bundle.home_currency:
            rejected.append((raw, "amount_is_not_in_home_currency"))
            continue
        period = raw.get("period_days")
        period_days = int(period) if isinstance(period, int) and 1 <= period <= 40 else None
        fact = ProposedFact(
            fact_type=fact_type, source_ids=sources, category=category,
            event_ids=event_ids, amount=amount, currency=currency or bundle.home_currency,
            effective_date=effective_date, period_days=period_days,
            scope=str(raw.get("scope") or "ongoing").strip(),
            certainty=certainty, rationale=str(raw.get("rationale") or "")[:400],
            unresolved_questions=_as_tuple(raw.get("unresolved_questions")))
        problem = _shape_problem(fact)
        if problem:
            rejected.append((raw, problem))
            continue
        accepted.append(fact)
        unresolved.extend(fact.unresolved_questions)

    return FactReview(tuple(accepted), tuple(rejected), tuple(unresolved))


def _shape_problem(fact):
    """Per-type required fields, so a half-filled claim cannot move money."""
    if fact.fact_type == "event_amount":
        if not fact.event_ids or fact.amount is None:
            return "event_amount_requires_event_ids_and_amount"
    if fact.fact_type == "exclude_event" and not fact.event_ids:
        return "exclude_event_requires_event_ids"
    if fact.fact_type in ("income_amount_change", "recurring_expense_amount_change"):
        if fact.amount is None or not fact.category:
            return "amount_change_requires_category_and_amount"
    if fact.fact_type in ("new_recurring_expense", "new_recurring_income"):
        if fact.amount is None or fact.effective_date is None:
            return fact.fact_type + "_requires_amount_and_start_date"
    if fact.fact_type in ("income_stream_ends", "exclude_projection") and not fact.category:
        return "series_level_fact_requires_category"
    if fact.fact_type == "income_date_change" and fact.effective_date is None:
        return "income_date_change_requires_effective_date"
    return ""


def apply_event_facts(bundle, review):
    """Fill image-supplied amounts and drop rows an update says are not cash."""
    amounts, excluded = {}, {}
    for fact in review.accepted:
        if fact.fact_type == "event_amount":
            for event_id in fact.event_ids:
                amounts[event_id] = quantize(fact.amount)
        elif fact.fact_type == "exclude_event" or (
                fact.fact_type == "exclude_projection" and fact.scope == "single_event"):
            for event_id in fact.event_ids:
                excluded[event_id] = "excluded_by_" + ",".join(fact.source_ids)
    if not amounts and not excluded:
        return bundle
    updated = []
    for event in bundle.events:
        if event.event_id in amounts and event.amount is None:
            filled = amounts[event.event_id]
            event = replace(event, amount=filled, home_amount=filled, currency=bundle.home_currency)
        if event.event_id in excluded:
            event = replace(event, exclusion_reason=excluded[event.event_id])
        updated.append(event)
    bundle.events = updated
    bundle.unknown_amount_event_ids = tuple(
        e.event_id for e in updated if e.amount is None)
    return bundle


#: Employment income is the backbone of a forecast. A claim may only stop it
#: when it names the exact pattern, so a note about an unapproved bonus can
#: never silently erase the salary the bonus would have topped up.
PROTECTED_STREAMS = frozenset({"payroll"})


def _targets(series, fact, direction=None):
    """Match a claim to a pattern by event id first, then by category.

    Event ids are the precise handle: a user can have payroll and an unapproved
    quarterly bonus in the same category, and only one of them should stop.
    """
    if direction and series.direction != direction:
        return False
    if fact.event_ids:
        named = set(fact.event_ids)
        if series.last_event_id in named or named & set(series.supporting_event_ids):
            return True
        return False
    return bool(fact.category) and series.category == fact.category


def _may_suppress(series, fact):
    """Guard the difference between "this pattern stops" and "this one row is odd".

    A note about a one-off arrears line inside an otherwise normal payslip must
    never delete the salary it was attached to.
    """
    if fact.scope == "single_event":
        return False
    if series.stream in PROTECTED_STREAMS:
        return bool(fact.event_ids)
    return True


def apply_series_facts(bundle, series_list, review):
    """Amend, cancel or extend recurring patterns using validated claims only."""
    result = list(series_list)
    for fact in review.accepted:
        if fact.fact_type == "income_stream_ends":
            for series in result:
                if _targets(series, fact, "credit") and _may_suppress(series, fact):
                    series.active = False
                    series.suppressed_reason = "income_ended_per_" + ",".join(fact.source_ids)
                    series.override_sources = fact.source_ids
        elif fact.fact_type == "exclude_projection":
            for series in result:
                if _targets(series, fact) and _may_suppress(series, fact):
                    series.active = False
                    series.suppressed_reason = "not_projectable_per_" + ",".join(fact.source_ids)
                    series.override_sources = fact.source_ids
        elif fact.fact_type in ("income_amount_change", "recurring_expense_amount_change"):
            wanted = "credit" if fact.fact_type == "income_amount_change" else "debit"
            for series in result:
                if _targets(series, fact, wanted):
                    series.amount_override = quantize(fact.amount)
                    series.override_scope = fact.scope
                    series.override_sources = fact.source_ids
        elif fact.fact_type == "income_date_change":
            for series in result:
                if _targets(series, fact, "credit") or (
                        not fact.event_ids and not fact.category
                        and series.direction == "credit"):
                    series.date_override = fact.effective_date
                    series.override_scope = "next_occurrence"
                    series.override_sources = fact.source_ids
        elif fact.fact_type == "new_recurring_expense":
            result.append(_new_series(bundle, fact, "debit"))
        elif fact.fact_type == "new_recurring_income":
            # An announcement never stacks on top of income the history already
            # shows: if the stream is already projected, this amends it instead.
            existing = [s for s in result if s.direction == "credit" and s.active
                        and (not fact.category or s.category == fact.category)]
            if existing:
                for series in existing:
                    series.amount_override = quantize(fact.amount)
                    series.date_override = fact.effective_date
                    series.override_scope = fact.scope
                    series.override_sources = fact.source_ids
            else:
                result.append(_new_series(bundle, fact, "credit"))
    return result


def _new_series(bundle, fact, direction):
    """A commitment or income stream the evidence announces but history lacks."""
    period = fact.period_days or 30
    credit = direction == "credit"
    category = fact.category or ("salary" if credit else "other")
    event_type = "income" if credit else "expense"
    # Anchor one period before the announced start so the first projected
    # occurrence lands exactly on the confirmed date. Monthly patterns step by
    # calendar month, so the anchor has to step back the same way.
    monthly = 26 <= period <= 33
    anchor = (add_months(fact.effective_date, -1) if monthly
              else fact.effective_date - timedelta(days=period))
    return Series(
        key=(event_type, category, direction),
        event_type=event_type, category=category, direction=direction,
        period_days=period, monthly=monthly, amount=quantize(fact.amount),
        last_date=anchor, last_event_id="",
        descriptions=("reported new " + ("income" if credit else "commitment"),),
        occurrences=0, supporting_event_ids=fact.source_ids, flexibility="fixed",
        minimum_allowed_amount=None,
        stream="payroll" if credit else "",
        extra_note="added from " + ",".join(fact.source_ids))
