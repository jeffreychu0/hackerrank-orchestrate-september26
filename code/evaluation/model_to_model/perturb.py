"""Known-defect injection: the only way this eval can measure its own judges.

Cross-examination alone cannot say whether a judge is any good. On the sample
set the two providers produce the same output row 24 times in 25, so there is
almost never a case where exactly one of them was right - the calibration table
comes back empty, and a scorecard that cannot be checked is not evidence.

So a second calibration path injects defects whose correct verdict is known by
construction: take a real reading, damage it in one specific way, and show the
pair to the judge blind. A judge that cannot reliably prefer the undamaged
reading is not measuring evidence fidelity, whatever its verdicts look like.

The defects are the failure modes deterministic validation cannot catch. The
validator already refuses an unknown source, an unowned event, an invented
category or an impossible date; nothing in code can tell that a one-off
adjustment was silently promoted to a permanent one.
"""

import copy
from dataclasses import dataclass

#: Ordered so that `--calibrate` reports the most damaging defects first.
DEFECTS = ("scope_inflation", "certainty_promotion", "amount_drift",
           "scope_overreach", "claim_omission", "claim_invention")


@dataclass(frozen=True)
class Perturbation:
    request_id: str
    defect: str
    original: list
    damaged: list
    note: str

    @property
    def describes(self):
        return "{} ({})".format(self.defect, self.note)


def _copy(claims):
    return copy.deepcopy(list(claims))


def scope_inflation(claims):
    """A one-off adjustment silently becomes the user's new normal."""
    damaged = _copy(claims)
    for claim in damaged:
        if claim.get("scope") == "next_occurrence":
            claim["scope"] = "ongoing"
            return damaged, "next_occurrence promoted to ongoing"
    return None, ""


def certainty_promotion(claims):
    """A hedged statement is recorded as settled fact, which unlocks cash."""
    damaged = _copy(claims)
    for claim in damaged:
        if claim.get("certainty") in ("likely", "unconfirmed"):
            claim["certainty"] = "confirmed"
            return damaged, "unconfirmed evidence marked confirmed"
    return None, ""


def amount_drift(claims):
    """An amount the evidence states is quietly replaced by a nearby one."""
    damaged = _copy(claims)
    for claim in damaged:
        raw = claim.get("amount")
        if raw:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value:
                claim["amount"] = "{:.2f}".format(value * 1.18)
                return damaged, "amount inflated by 18% against the evidence"
    return None, ""


def scope_overreach(claims):
    """A claim about one pattern is widened to the whole category."""
    damaged = _copy(claims)
    for claim in damaged:
        if claim.get("event_ids"):
            claim["event_ids"] = []
            claim["scope"] = "ongoing"
            return damaged, "named pattern widened to the entire category"
    return None, ""


def claim_omission(claims):
    """The reader simply misses a material fact."""
    if len(claims) < 1:
        return None, ""
    damaged = _copy(claims)
    dropped = damaged.pop(0)
    return damaged, "dropped the {} claim".format(dropped.get("fact_type", "first"))


def claim_invention(claims):
    """The reader asserts a commitment the evidence never mentions."""
    if not claims:
        return None, ""
    damaged = _copy(claims)
    source = claims[0].get("source_ids", [])
    damaged.append({
        "fact_type": "new_recurring_expense", "source_ids": list(source),
        "category": claims[0].get("category") or "other", "event_ids": [],
        "amount": "250.00", "effective_date": claims[0].get("effective_date"),
        "period_days": 30, "scope": "ongoing", "certainty": "confirmed",
        "rationale": "A new monthly commitment starts alongside this change.",
        "unresolved_questions": [],
    })
    return damaged, "added a commitment the evidence never states"


INJECTORS = {
    "scope_inflation": scope_inflation,
    "certainty_promotion": certainty_promotion,
    "amount_drift": amount_drift,
    "scope_overreach": scope_overreach,
    "claim_omission": claim_omission,
    "claim_invention": claim_invention,
}


def build(audits, *, provider, defects=DEFECTS, limit=None, request_ids=()):
    """One perturbation per (request, applicable defect), from a real reading."""
    source = audits[provider]
    chosen = []
    for request_id in sorted(source, key=_sort_key):
        if request_ids and request_id not in request_ids:
            continue
        claims = source[request_id].get("accepted_claims", [])
        if not claims:
            continue
        for defect in defects:
            damaged, note = INJECTORS[defect](claims)
            if damaged is None or damaged == claims:
                continue
            chosen.append(Perturbation(request_id, defect, list(claims),
                                       damaged, note))
            if limit and len(chosen) >= limit:
                return chosen
    return chosen


def _sort_key(request_id):
    tail = request_id.split("_")[-1]
    return (0, int(tail)) if tail.isdigit() else (1, request_id)


def coverage(perturbations):
    from collections import Counter
    return Counter(p.defect for p in perturbations)
