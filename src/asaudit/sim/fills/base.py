"""Fill-model contract.

Deviation from the PRD sketch, recorded in DECISIONS 2026-09-28: events arrive
as a row range over the columnar ``ReplaySession`` instead of a sequence of
``LOBEvent`` objects, and a ``StepContext`` carries the mid and segment length
that the Poisson model needs. Semantics are unchanged.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from asaudit.sim.competition.base import CompetitionModel
from asaudit.sim.session import ReplaySession
from asaudit.types import Fill, OwnOrderState, Side


@dataclass(frozen=True, slots=True)
class StepContext:
    ts_ns: int
    end_ns: int
    mid: float
    session: ReplaySession | None
    row_lo: int
    row_hi: int
    competition: CompetitionModel

    @property
    def dt_s(self) -> float:
        return (self.end_ns - self.ts_ns) / 1e9


class FillModel(Protocol):
    name: str
    #: True when fills are driven by observed flow and so carry real adverse selection.
    embeds_adverse_selection: bool

    def place(
        self, order_id: int, side: Side, price: int, size: int, ctx: StepContext
    ) -> OwnOrderState:
        """New order at the back of the queue at ``price`` (row ``ctx.row_lo``)."""
        ...

    def step(
        self,
        own_orders: Mapping[int, OwnOrderState],
        ctx: StepContext,
        rng: np.random.Generator,
    ) -> tuple[list[Fill], dict[int, OwnOrderState]]:
        """Advance own orders through [ctx.ts_ns, ctx.end_ns); return fills, new state."""
        ...
