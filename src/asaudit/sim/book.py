"""Bounded aggregate reconstruction with explicitly supplied boundary state.

No initial order identities or queue priority are inferred. A reference level
can enter only beyond the previous observed boundary or through a checked ADD.
"""

from dataclasses import dataclass

from asaudit.types import BookSnapshot, EventType, LOBEvent, Side


@dataclass(frozen=True, slots=True)
class SuppliedLevel:
    side: Side
    price_ticks: int
    size: int


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    supplied_boundary_levels: int
    independently_checked_levels: int
    supplied_levels: tuple[SuppliedLevel, ...]


class BoundedBook:
    def __init__(self, initial: BookSnapshot) -> None:
        self.snapshot = initial

    def advance(self, event: LOBEvent, observed: BookSnapshot) -> ReconstructionResult:
        supplied = checked = 0
        provenance: list[SuppliedLevel] = []
        if event.ts_ns != observed.ts_ns:
            raise ValueError("event and snapshot timestamps do not align")
        for side, old_px, old_sz, new_px, new_sz in [
            (
                Side.BID,
                self.snapshot.bid_px_ticks,
                self.snapshot.bid_sz,
                observed.bid_px_ticks,
                observed.bid_sz,
            ),
            (
                Side.ASK,
                self.snapshot.ask_px_ticks,
                self.snapshot.ask_sz,
                observed.ask_px_ticks,
                observed.ask_sz,
            ),
        ]:
            known = {int(p): int(s) for p, s in zip(old_px, old_sz, strict=True)}
            actual = {int(p): int(s) for p, s in zip(new_px, new_sz, strict=True)}
            previous_boundary = int(old_px[-1]) if len(old_px) else None
            complete_side = len(old_px) < self.snapshot.level_capacity
            if event.side is side and event.event_type in (
                EventType.ADD,
                EventType.CANCEL,
                EventType.DELETE,
                EventType.EXECUTE,
            ):
                price = event.price_ticks
                if price is None:
                    raise ValueError("book event has no price")
                if event.event_type is EventType.ADD:
                    # An unknown price inside the visible interval has zero
                    # previous depth. Beyond the interval its depth is unknown.
                    inside = (
                        complete_side
                        or previous_boundary is None
                        or (price - previous_boundary) * int(side) >= 0
                    )
                    if price in known or inside:
                        known[price] = known.get(price, 0) + event.size
                elif price in known:
                    remaining = known[price] - event.size
                    if remaining < 0:
                        raise ValueError("event removes more than visible level depth")
                    if remaining:
                        known[price] = remaining
                    else:
                        del known[price]
                elif previous_boundary is not None and (price - previous_boundary) * int(side) >= 0:
                    raise ValueError("removal from absent visible price")
            for price, size in actual.items():
                if price in known:
                    if known[price] != size:
                        raise ValueError(
                            f"retained/event level mismatch at {price}: {known[price]} != {size}"
                        )
                    checked += 1
                else:
                    # Only a genuinely unobserved less-competitive price may be
                    # imported. An absent level within the old range is known zero.
                    if (
                        complete_side
                        or previous_boundary is None
                        or (price - previous_boundary) * int(side) >= 0
                    ):
                        raise ValueError(f"unexpected interior level mismatch at {price}")
                    if (
                        event.side is side
                        and event.event_type is EventType.ADD
                        and event.price_ticks == price
                        and size < event.size
                    ):
                        raise ValueError("boundary size smaller than known ADD")
                    supplied += 1
                    provenance.append(SuppliedLevel(side, price, size))
            for price in known.keys() - actual.keys():
                if not len(new_px) or (price - int(new_px[-1])) * int(side) >= 0:
                    raise ValueError(f"visible level disappeared without event at {price}")
        self.snapshot = observed
        return ReconstructionResult(supplied, checked, tuple(provenance))
