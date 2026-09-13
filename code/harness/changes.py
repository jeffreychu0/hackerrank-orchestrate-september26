"""Permitted spending changes: the last resort, searched least-intrusive first.

A change is only ever proposed against a detected recurring series whose
category the user permits and whose flexibility allows the action. It reduces
future occurrences; it never refunds a settled expense. Feasibility is proved
by re-running the whole forecast, not by comparing a shortfall to one month of
savings.
"""

from dataclasses import dataclass
from decimal import Decimal

from .config import MAX_SPENDING_CHANGES
from .money import ZERO, quantize
from .recurrence import latest_occurrence


@dataclass(frozen=True)
class SpendingChange:
    """One ``stop:`` or ``reduce_to:`` action against a named event row."""

    action: str            # "stop" | "reduce_to"
    event_id: str
    category: str
    current_amount: Decimal
    new_amount: Decimal

    @property
    def saving(self):
        return self.current_amount - self.new_amount

    def render(self):
        from .money import plan_amount
        if self.action == "stop":
            return "stop:{}".format(self.event_id)
        return "reduce_to:{}:{}".format(self.event_id, plan_amount(self.new_amount))


def candidates(bundle, series_list):
    """Permitted actions, cheapest saving first, so the smallest cut is tried first."""
    found = []
    for series in series_list:
        if series.direction != "debit" or not series.active:
            continue
        if series.category in bundle.protected_categories:
            continue
        anchor = latest_occurrence(bundle, series)
        if anchor is None:
            continue
        current = series.effective_amount
        if current <= ZERO:
            continue
        flexibility = series.flexibility or ""
        if ("reducible" in flexibility and series.category in bundle.reducible_categories
                and anchor.minimum_allowed_amount is not None):
            floor = quantize(anchor.minimum_allowed_amount)
            if ZERO <= floor < current:
                found.append(SpendingChange("reduce_to", anchor.event_id, series.category,
                                            current, floor))
        if "stoppable" in flexibility and series.category in bundle.stoppable_categories:
            found.append(SpendingChange("stop", anchor.event_id, series.category,
                                        current, ZERO))
    found.sort(key=lambda c: (c.saving, c.event_id, c.action))
    return found


def search(bundle, series_list, plan_builder, *, limit=MAX_SPENDING_CHANGES):
    """Add the least-intrusive permitted changes until a plan becomes feasible.

    ``plan_builder(changes)`` returns the best candidate under those changes, or
    None. Returns ``(candidate, changes)``; ``(None, ())`` when no permitted
    combination of at most ``limit`` changes produces an eligible safe plan.
    """
    options = candidates(bundle, series_list)
    if not options:
        return None, ()
    chosen = {}
    for option in options:
        previous = chosen.get(option.event_id)
        if previous is None and len(chosen) >= limit:
            continue
        # Stopping and reducing the same event are mutually exclusive: a later,
        # larger action on the same row replaces the smaller one.
        chosen[option.event_id] = option
        selection = _ordered(chosen)
        candidate = plan_builder(selection)
        if candidate is not None:
            return candidate, selection
        if previous is not None and previous.saving > option.saving:
            chosen[option.event_id] = previous
    return None, ()


def _ordered(chosen):
    return tuple(sorted(chosen.values(), key=lambda c: (c.event_id, c.action)))


def render_all(changes):
    return "|".join(change.render() for change in changes) if changes else "none"
