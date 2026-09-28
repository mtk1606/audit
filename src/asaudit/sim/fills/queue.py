"""A1 on: FIFO queue position against replayed L3 flow.

Our order is virtual (zero own impact). ``queue_ahead`` starts at the visible
depth at our price when the order is placed (back of the queue) and changes only
through:

- visible executions at our price, which consume queue ahead first, then us;
- executions at a price through ours, which prove our level was exhausted, so
  their volume fills us first;
- cancellations at our price, of which a policy-dependent share is ahead of us
  (PRD 4.3): pessimistic none, optimistic all (up to queue_ahead), uniform a
  Binomial(size, queue_ahead / depth) draw, which is the proportional rule;
- a clamp to the visible level depth after every event, since no more volume
  can be ahead of us than rests at the level.

Hidden executions do not interact with the visible queue: they neither fill us
nor move queue_ahead. This is conservative (it can only lower fill counts).
A3 scales the ahead share of cancellations by the competition model's cancel
multiplier, with stochastic rounding.
"""

from collections.abc import Mapping
from typing import Literal

import numpy as np

from asaudit.sim.fills.base import StepContext
from asaudit.sim.session import ReplaySession
from asaudit.types import EventType, Fill, OwnOrderState, Side

CancelPolicy = Literal["pessimistic", "uniform", "optimistic"]
_EXEC, _HIDDEN = int(EventType.EXECUTE), int(EventType.EXECUTE_HIDDEN)
_CANCELS = (int(EventType.CANCEL), int(EventType.DELETE))


def crossed(s: ReplaySession, row: int, side: int, price: int) -> bool:
    """True when ``price`` is at or through the opposite touch at book ``row``."""
    if side == int(Side.BID):
        return bool(s.ask_sz[row, 0] > 0 and price >= s.ask_px[row, 0])
    return bool(s.bid_sz[row, 0] > 0 and price <= s.bid_px[row, 0])


class UnobservableQueue(ValueError):
    """Quote rests beyond the visible depth, where queue position is unknown."""


class QueueFillModel:
    name = "queue"
    embeds_adverse_selection = True

    def __init__(self, policy: CancelPolicy) -> None:
        if policy not in ("pessimistic", "uniform", "optimistic"):
            raise ValueError(f"unknown cancel attribution policy: {policy}")
        self.policy = policy

    @staticmethod
    def _session(ctx: StepContext) -> ReplaySession:
        if ctx.session is None:
            raise ValueError("queue fills require a replay session")
        return ctx.session

    def place(
        self, order_id: int, side: Side, price: int, size: int, ctx: StepContext
    ) -> OwnOrderState:
        s = self._session(ctx)
        row = ctx.row_lo
        px, sz = (
            (s.bid_px[row], s.bid_sz[row]) if side is Side.BID else (s.ask_px[row], s.ask_sz[row])
        )
        visible = px[sz > 0]
        depth = s.level_depth(row, int(side), price)
        if depth == 0 and len(visible) == s.depth:
            beyond = (price - int(visible[-1])) * int(side) < 0
            if beyond:
                raise UnobservableQueue("quote beyond visible depth: queue position unobservable")
        return OwnOrderState(order_id, side, price, size, depth, ctx.ts_ns)

    def step(
        self,
        own_orders: Mapping[int, OwnOrderState],
        ctx: StepContext,
        rng: np.random.Generator,
    ) -> tuple[list[Fill], dict[int, OwnOrderState]]:
        s = self._session(ctx)
        state = {oid: [o.queue_ahead, o.size_remaining] for oid, o in own_orders.items()}
        entry = {oid: o.queue_ahead for oid, o in own_orders.items()}
        fills: list[Fill] = []
        for i in range(ctx.row_lo, ctx.row_hi):
            etype, eside = int(s.event_type[i]), int(s.side[i])
            eprice, esize = int(s.price[i]), int(s.size[i])
            for oid, order in own_orders.items():
                ahead, left = state[oid]
                if left == 0 or eside != int(order.side):
                    continue
                side = int(order.side)
                filled = 0
                if crossed(s, i, side, order.price_ticks):
                    # At or through the opposite touch we would be a taker; the
                    # passive model grants no fill until the book uncrosses us.
                    continue
                if etype == _EXEC and eprice == order.price_ticks:
                    consumed = min(ahead, esize)
                    ahead -= consumed
                    filled = min(left, esize - consumed)
                elif etype == _EXEC and (eprice - order.price_ticks) * side < 0:
                    # Execution through our price: our level was exhausted first.
                    ahead = 0
                    filled = min(left, esize)
                elif etype in _CANCELS and eprice == order.price_ticks and ahead > 0:
                    depth_before = s.level_depth(i, side, order.price_ticks)
                    if self.policy == "optimistic":
                        cancelled_ahead = min(esize, ahead)
                    elif self.policy == "uniform" and depth_before > 0:
                        share = min(1.0, ahead / depth_before)
                        cancelled_ahead = min(ahead, int(rng.binomial(esize, share)))
                    else:
                        cancelled_ahead = 0
                    if cancelled_ahead:
                        adj = ctx.competition.adjust_intensities(
                            depth_before + left, depth_before, None
                        )
                        scaled = cancelled_ahead * adj.cancel_multiplier
                        whole = int(scaled)
                        whole += int(rng.random() < scaled - whole)
                        ahead -= min(ahead, whole)
                if filled:
                    left -= filled
                    mid = s.mid(i)
                    fills.append(
                        Fill(
                            int(s.ts_ns[i]),
                            order.side,
                            order.price_ticks,
                            filled,
                            entry[oid],
                            ahead,
                            mid,
                            True,
                        )
                    )
                if eprice == order.price_ticks:
                    # No more volume can be ahead than rests at the level afterwards.
                    ahead = min(ahead, s.level_depth(i + 1, side, order.price_ticks))
                state[oid] = [ahead, left]
        out = {
            oid: OwnOrderState(
                o.order_id, o.side, o.price_ticks, state[oid][1], state[oid][0], o.entry_ts_ns
            )
            for oid, o in own_orders.items()
            if state[oid][1] > 0
        }
        return fills, out
