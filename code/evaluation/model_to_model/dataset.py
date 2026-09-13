"""Build the adjudication set from two provider runs.

The sample answers cover 25 requests. This eval covers any request in the
dataset, at the cost of having no ground truth: instead of asking "is this
right", it asks "which of two independent readings of the same evidence is
better supported", and it asks a model that did not produce either reading.

Only the interpretation step is judged. Everything downstream is deterministic,
so a judge could not out-reason it, and anything it disagreed with there would
be a complaint about arithmetic rather than about evidence.
"""

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

ROW_FIELDS = ("amount_safe_to_pay", "affordability_status",
              "recommended_payment_method", "payment_plan",
              "earliest_date_for_full_payment", "spending_changes_needed")


@dataclass
class Item:
    """One request, with both readings of its evidence, presented blind."""

    request_id: str
    producers: tuple            # (producer of reading_1, producer of reading_2)
    reading_1: list             # claims, already shuffled into position
    reading_2: list
    claims_differ: bool
    row_fields_differ: tuple    # which output fields the two runs disagree on
    rows: dict = field(default_factory=dict)

    @property
    def swapped(self):
        """True when reading_1 came from the second-named provider."""
        return self.producers[0] != self.producers[1] and self.producers[0] != self._first

    def producer_of(self, verdict):
        """Map a blind verdict back to the provider that produced it."""
        if verdict == "reading_1":
            return self.producers[0]
        if verdict == "reading_2":
            return self.producers[1]
        return verdict


def load_audit(path):
    """Read one run's audit trail, keyed by request id."""
    rows = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                record = json.loads(line)
                rows[record["request_id"]] = record
    return rows


def load_rows(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        return {row["request_id"]: row for row in csv.DictReader(handle)}


def _normalise(claims):
    """Claim content without the prose, so ordering and wording do not count."""
    keys = ("fact_type", "category", "event_ids", "amount", "effective_date",
            "scope", "certainty", "source_ids")
    return sorted(json.dumps({k: claim.get(k) for k in keys}, sort_keys=True)
                  for claim in claims)


def _order(request_id, salt):
    """Deterministic per-request coin flip, so presentation order is not a tell.

    Seeded from the request id rather than a global RNG so the same eval set
    rebuilds identically, and a judge cannot learn that position 1 is always
    the same provider.
    """
    digest = hashlib.sha256("{}:{}".format(salt, request_id).encode("utf-8")).digest()
    return digest[0] % 2 == 0


def build(audits, rows_by_provider, *, providers, salt="model_to_model",
          only_disagreements=False, limit=None, request_ids=()):
    """Assemble items from two provider runs.

    ``audits`` and ``rows_by_provider`` are dicts keyed by provider name.
    """
    first, second = providers
    shared = set(audits[first]) & set(audits[second])
    if request_ids:
        shared &= set(request_ids)
    items = []
    for request_id in sorted(shared, key=_request_sort_key):
        claims = {p: audits[p][request_id].get("accepted_claims", []) for p in providers}
        differ = _normalise(claims[first]) != _normalise(claims[second])
        row_first = rows_by_provider.get(first, {}).get(request_id, {})
        row_second = rows_by_provider.get(second, {}).get(request_id, {})
        changed = tuple(f for f in ROW_FIELDS
                        if row_first.get(f) != row_second.get(f))
        if only_disagreements and not differ:
            continue
        # Both readings must contain something to compare.
        if not claims[first] and not claims[second]:
            continue
        forward = _order(request_id, salt)
        order = (first, second) if forward else (second, first)
        item = Item(request_id=request_id, producers=order,
                    reading_1=claims[order[0]], reading_2=claims[order[1]],
                    claims_differ=differ, row_fields_differ=changed,
                    rows={first: row_first, second: row_second})
        item._first = first
        items.append(item)
        if limit and len(items) >= limit:
            break
    return items


def _request_sort_key(request_id):
    tail = request_id.split("_")[-1]
    return (0, int(tail)) if tail.isdigit() else (1, request_id)


def summarise(items):
    return {
        "items": len(items),
        "claims_differ": sum(1 for i in items if i.claims_differ),
        "output_row_differs": sum(1 for i in items if i.row_fields_differ),
        "claims_differ_without_output_change": sum(
            1 for i in items if i.claims_differ and not i.row_fields_differ),
    }
