"""Output contract enforcement and CSV writing.

A row that would violate the published contract is caught here rather than at
scoring time: bad enum values, an out-of-range safe amount, a partial plan that
does not sum to the request, an installment plan that does not match a supplied
offer, or more than three spending changes.
"""

import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from .money import ZERO, parse, quantize

COLUMNS = ("request_id", "amount_safe_to_pay", "affordability_status",
           "recommended_payment_method", "payment_plan",
           "earliest_date_for_full_payment", "spending_changes_needed",
           "decision_explanation")

STATUSES = frozenset({"affordable_now", "affordable_with_plan",
                      "affordable_later", "not_affordable"})
METHODS = frozenset({"full_payment", "partial_payment", "installments",
                     "wait", "not_recommended"})


class ContractError(ValueError):
    """The produced row would break the required output contract."""


def parse_plan(text):
    if text == "none":
        return []
    entries = []
    for chunk in text.split("|"):
        when, _, amount = chunk.partition(":")
        entries.append((date.fromisoformat(when), Decimal(amount)))
    return entries


def validate_row(row, bundle):
    """Check one finished row against every published invariant."""
    problems = []
    if row["request_id"] != bundle.request["request_id"]:
        problems.append("request_id_mismatch")
    try:
        safe = Decimal(row["amount_safe_to_pay"])
    except (InvalidOperation, ValueError):
        return ["amount_safe_to_pay_is_not_a_number"]
    if not ZERO <= safe <= bundle.requested_amount:
        problems.append("amount_safe_to_pay_outside_zero_to_requested_amount")
    status = row["affordability_status"]
    method = row["recommended_payment_method"]
    if status not in STATUSES:
        problems.append("invalid_affordability_status")
    if method not in METHODS:
        problems.append("invalid_recommended_payment_method")

    plan = row["payment_plan"]
    try:
        payments = parse_plan(plan)
    except (ValueError, InvalidOperation):
        return problems + ["payment_plan_is_malformed"]
    if payments != sorted(payments, key=lambda p: p[0]):
        problems.append("payment_plan_is_not_chronological")
    if method == "not_recommended" and plan != "none":
        problems.append("not_recommended_must_have_no_payment_plan")
    if method != "not_recommended" and not payments:
        problems.append("recommended_method_requires_a_payment_plan")

    earliest = row["earliest_date_for_full_payment"]
    if earliest:
        try:
            earliest_date = date.fromisoformat(earliest)
        except ValueError:
            problems.append("earliest_date_is_not_iso")
            earliest_date = None
    else:
        earliest_date = None
    if status == "affordable_now" and earliest_date != bundle.as_of:
        problems.append("affordable_now_requires_earliest_date_equal_to_request_date")

    if method == "partial_payment":
        if status != "affordable_with_plan":
            problems.append("partial_payment_requires_affordable_with_plan")
        if not bundle.allows_partial:
            problems.append("partial_payment_not_permitted_by_request")
        if "partial_payment" not in bundle.accepted_methods:
            problems.append("partial_payment_not_accepted_by_user")
        if len(payments) != 2:
            problems.append("partial_payment_requires_exactly_two_payments")
        else:
            if sum(amount for _, amount in payments) != quantize(bundle.requested_amount):
                problems.append("partial_payments_do_not_sum_to_requested_amount")
            if payments[0][0] != bundle.as_of:
                problems.append("partial_first_payment_must_be_on_request_date")
            if earliest_date is None or payments[1][0] != earliest_date:
                problems.append("partial_second_payment_must_be_on_earliest_full_payment_date")
            if payments[1][0] > bundle.deadline:
                problems.append("partial_payment_completes_after_desired_completion_date")
            if not ZERO < safe < bundle.requested_amount:
                problems.append("partial_payment_requires_safe_amount_strictly_inside_request")

    if method == "installments":
        matched = False
        for option in bundle.options:
            if option["payment_method"] != "installments":
                continue
            from .plans import schedule_for
            if list(schedule_for(option, bundle.as_of)) == payments:
                matched = True
                break
        if not matched:
            problems.append("installment_plan_does_not_match_a_supplied_option")

    if method == "full_payment" and len(payments) == 1:
        if payments[0][1] != quantize(bundle.requested_amount):
            problems.append("full_payment_must_equal_requested_amount")

    changes = row["spending_changes_needed"]
    if changes != "none":
        actions = changes.split("|")
        if len(actions) > 3:
            problems.append("more_than_three_spending_changes")
        seen = {}
        for action in actions:
            parts = action.split(":")
            if parts[0] == "stop" and len(parts) == 2:
                event_id, kind = parts[1], "stop"
            elif parts[0] == "reduce_to" and len(parts) == 3:
                event_id, kind = parts[1], "reduce_to"
            else:
                problems.append("malformed_spending_change")
                continue
            event = bundle.event(event_id)
            if event is None:
                problems.append("spending_change_event_not_owned_by_user")
                continue
            if event.category in bundle.protected_categories:
                problems.append("spending_change_targets_a_protected_category")
            if event_id in seen:
                problems.append("stop_and_reduce_target_the_same_event")
            seen[event_id] = kind

    if not row["decision_explanation"].strip():
        problems.append("empty_decision_explanation")
    return problems


def write(rows, path, order):
    """Write exactly one row per evaluation request, in dataset order."""
    by_id = {row["request_id"]: row for row in rows}
    missing = [request_id for request_id in order if request_id not in by_id]
    if missing:
        raise ContractError("Missing output rows for: " + ", ".join(missing[:5]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for request_id in order:
            writer.writerow({column: by_id[request_id][column] for column in COLUMNS})
    return len(order)
