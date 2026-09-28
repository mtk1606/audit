"""A1 off: AS fills, lambda(delta) = A * exp(-k * delta), independent of flow.

``delta`` is the distance from mid in source price quanta. ``rule`` fixes how
lambda * dt maps to a probability; ``saturate`` is the law identified in
docs/reports/M1-sensitivity.md, and is the default so (off, off, off) reduces
to M1.
"""

import math
from collections.abc import Mapping
from typing import Literal

import numpy as np

from asaudit.sim.fills.base import StepContext
from asaudit.sim.fills.queue import crossed
from asaudit.types import Fill, OwnOrderState, Side


class PoissonFillModel:
    name = "poisson"
    embeds_adverse_selection = False

    def __init__(
        self, A: float, k: float, rule: Literal["saturate", "poisson"] = "saturate"
    ) -> None:
        if not (A >= 0 and k > 0 and math.isfinite(A) and math.isfinite(k)):
            raise ValueError("invalid intensity parameters")
        self.A, self.k, self.rule = A, k, rule

    def place(
        self, order_id: int, side: Side, price: int, size: int, ctx: StepContext
    ) -> OwnOrderState:
        return OwnOrderState(order_id, side, price, size, 0, ctx.ts_ns)

    def probability(self, distance: float, dt_s: float) -> float:
        rate = self.A * math.exp(-self.k * distance) * dt_s
        return min(rate, 1.0) if self.rule == "saturate" else -math.expm1(-rate)

    def step(
        self,
        own_orders: Mapping[int, OwnOrderState],
        ctx: StepContext,
        rng: np.random.Generator,
    ) -> tuple[list[Fill], dict[int, OwnOrderState]]:
        fills: list[Fill] = []
        remaining: dict[int, OwnOrderState] = {}
        # Deterministic draw order (bid before ask) keeps fixed-seed runs identical.
        for oid, order in sorted(own_orders.items(), key=lambda kv: -int(kv[1].side)):
            distance = int(order.side) * (ctx.mid - order.price_ticks)
            draw = rng.random()
            if ctx.session is not None and crossed(
                ctx.session, ctx.row_lo, int(order.side), order.price_ticks
            ):
                remaining[oid] = order  # would be a taker; no passive fill
                continue
            if draw < self.probability(distance, ctx.dt_s):
                fills.append(
                    Fill(
                        ctx.ts_ns,
                        order.side,
                        order.price_ticks,
                        order.size_remaining,
                        0,
                        0,
                        ctx.mid,
                        False,
                    )
                )
            else:
                remaining[oid] = order
        return fills, remaining
