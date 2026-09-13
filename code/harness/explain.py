"""Explanations written from locked computed fields, never from model arithmetic.

The supplied examples explain decisions in a tight, repeatable house style, so
the default writer reproduces that style deterministically. The optional model
writer is given the same locked numbers and may only reword them.
"""

from decimal import Decimal

from .money import quantize

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")

MODEL_SYSTEM = """You write one-sentence-pair explanations for an already-decided financial recommendation.

Every number, date and action below is final and computed by a deterministic engine.
Restate them; never add, drop, recompute or soften a figure, and never introduce a fact
that is not listed. Two short sentences: what to do, then why it is safe. Plain English,
no markdown, no more than 40 words.
"""


def money(amount, currency):
    """Grouped home-currency figure: two decimals only when fractional."""
    amount = quantize(amount)
    if amount % 1:
        return "{} {:,.2f}".format(currency, amount)
    return "{} {:,}".format(currency, int(amount))


def long_date(value):
    return "{} {} {}".format(value.day, MONTHS[value.month - 1], value.year)


def _change_phrase(decision, change, bundle):
    event = bundle.event(change.event_id)
    label = (event.description if event else change.category).strip().lower()
    if change.action == "stop":
        return "stop the " + label
    return "reduce the {} to {}".format(label, money(change.new_amount, decision.currency))


def _joined(phrases):
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def template(decision, bundle):
    """The deterministic writer: one house-style explanation per method."""
    currency = decision.currency
    floor = money(decision.minimum_balance, currency)
    method = decision.recommended_payment_method

    if method == "full_payment":
        payment = money(decision.payments[0][1], currency)
        if decision.spending_changes:
            phrases = [_change_phrase(decision, change, bundle)
                       for change in decision.spending_changes]
            sentence = _joined(phrases)
            return "{}{}, then pay {} today. This leaves at least {} available.".format(
                sentence[0].upper(), sentence[1:], payment, floor)
        return ("Pay {} today. This leaves at least {} available over the next 90 days."
                .format(payment, floor))

    if method == "installments":
        count = len(decision.payments)
        each = money(decision.payments[0][1], currency)
        start = long_date(decision.payments[0][0])
        return ("Use {} installments of {}, starting {}. This leaves at least {} available."
                .format(count, each, start, floor))

    if method == "partial_payment":
        first = money(decision.payments[0][1], currency)
        second = money(decision.payments[1][1], currency)
        when = long_date(decision.payments[1][0])
        return ("Pay {} today and the remaining {} on {}. This completes the full request "
                "and keeps the {} minimum protected.".format(first, second, when, floor))

    if method == "wait":
        amount = money(decision.payments[0][1], currency)
        when = long_date(decision.payments[0][0])
        return ("Pay {} in full on {}. Paying earlier would take the balance below the {} "
                "minimum.".format(amount, when, floor))

    return ("Do not make this payment by {}. None of the available options keeps the {} "
            "minimum protected.".format(long_date(decision.deadline), floor))


def model_brief(decision, bundle):
    """The locked facts handed to the optional model writer."""
    lines = [
        "currency=" + decision.currency,
        "recommended_payment_method=" + decision.recommended_payment_method,
        "affordability_status=" + decision.affordability_status,
        "requested_amount=" + money(decision.requested_amount, decision.currency),
        "amount_safe_to_pay_today=" + money(decision.amount_safe_to_pay, decision.currency),
        "minimum_balance_to_keep=" + money(decision.minimum_balance, decision.currency),
        "lowest_projected_balance_under_this_plan=" + money(decision.projected_minimum,
                                                            decision.currency),
        "desired_completion_date=" + long_date(decision.deadline),
    ]
    if decision.earliest_date_for_full_payment:
        lines.append("earliest_safe_full_payment=" +
                     long_date(decision.earliest_date_for_full_payment))
    if decision.payments:
        lines.append("payments=" + "; ".join(
            "{} on {}".format(money(amount, decision.currency), long_date(when))
            for when, amount in decision.payments))
    else:
        lines.append("payments=none recommended")
    for change in decision.spending_changes:
        lines.append("spending_change=" + _change_phrase(decision, change, bundle))
    for summary in decision.fact_summaries:
        lines.append("evidence_applied=" + summary)
    lines.append("house_style_example=" + template(decision, bundle))
    return "\n".join(lines)


EXPLANATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["explanation"],
    "properties": {"explanation": {"type": "string"}},
}


def with_model(client, decision, bundle):
    """Reword the locked fields; fall back to the template on any failure."""
    payload, usage = client.structured(
        MODEL_SYSTEM, model_brief(decision, bundle), EXPLANATION_SCHEMA,
        schema_name="decision_explanation")
    text = " ".join(str(payload.get("explanation", "")).split())
    if not text:
        raise RuntimeError("Model returned an empty explanation.")
    return text, usage
