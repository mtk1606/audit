"""Synthetic L3 order flow with known ground truth, for fixtures and tests.

Zero-intelligence limit-order flow plus partially informed market orders.
Every mechanism the ablation measures is present with a known parameter, so
calibration code can be checked for recovery before it touches real data:

- A1: FIFO queues with per-order ids; cancels pick a uniformly random order.
- A2: market-order direction leans toward a latent fundamental price, so passive
  fills precede adverse mid moves.
- A3: join intensity scales as (depth / d0) ** join_elasticity and per-order
  cancel intensity as (depth / d0) ** (cancel_elasticity - 1).

This is a statistical stand-in, not market data. Results on it are labelled
fixture output everywhere they appear.
"""

import math
from collections import deque

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from asaudit.sim.session import ReplaySession
from asaudit.types import EventType


class SyntheticConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    duration_s: float = Field(default=300.0, gt=0)
    tick: int = Field(default=100, gt=0)
    start_price: int = Field(default=1_000_000, gt=0)
    depth: int = Field(default=10, ge=2)
    add_rate: float = Field(default=2.0, gt=0, description="adds/s at level 0 at depth d0")
    add_decay: float = Field(default=0.5, ge=0, description="per-level decay of add rate")
    d0: float = Field(default=20.0, gt=0)
    join_elasticity: float = Field(default=-0.4, le=0)
    cancel_rate: float = Field(default=0.1, gt=0, description="per-order cancels/s at d0")
    cancel_elasticity: float = Field(default=1.3, ge=0)
    market_rate: float = Field(default=2.0, gt=0)
    mean_order_size: float = Field(default=4.0, ge=1)
    mean_market_size: float = Field(default=8.0, ge=1)
    fundamental_vol: float = Field(default=2.0, ge=0, description="ticks per sqrt(s)")
    informed_weight: float = Field(default=0.35, ge=0, le=0.5)
    initial_level_size: int = Field(default=10, ge=1)


def _geometric(rng: np.random.Generator, mean: float) -> int:
    return int(rng.geometric(1 / mean)) if mean > 1 else 1


def generate_session(
    cfg: SyntheticConfig,
    rng: np.random.Generator,
    session_id: str,
    start_ns: int = 0,
    symbol: str = "SYN",
) -> ReplaySession:
    tick, depth = cfg.tick, cfg.depth
    books: dict[int, dict[int, deque[list[int]]]] = {1: {}, -1: {}}
    next_id = 1
    for level in range(depth):
        for side in (1, -1):
            price = cfg.start_price - side * (level + 1) * tick
            books[side][price] = deque([[next_id, cfg.initial_level_size]])
            next_id += 1
    fundamental = float(cfg.start_price)
    rows: list[tuple[int, int, int, int, int, int]] = []
    snaps: list[tuple[list[int], list[int], list[int], list[int]]] = []

    def best(side: int) -> int | None:
        levels = [p for p, q in books[side].items() if q]
        if not levels:
            return None
        return max(levels) if side == 1 else min(levels)

    def level_size(side: int, price: int) -> int:
        return sum(o[1] for o in books[side].get(price, ()))

    def snapshot() -> tuple[list[int], list[int], list[int], list[int]]:
        out: list[list[int]] = []
        for side in (1, -1):
            prices = sorted((p for p, q in books[side].items() if q), reverse=side == 1)[:depth]
            sizes = [level_size(side, p) for p in prices]
            out += [prices + [0] * (depth - len(prices)), sizes + [0] * (depth - len(sizes))]
        return out[0], out[1], out[2], out[3]

    snaps.append(snapshot())
    t = 0.0
    horizon = cfg.duration_s
    while True:
        bb, ba = best(1), best(-1)
        ref = {
            1: ba if ba is not None else round(fundamental / tick) * tick + tick,
            -1: bb if bb is not None else round(fundamental / tick) * tick - tick,
        }
        # Candidate channels: (kind, side, price, rate).
        channels: list[tuple[int, int, int, float]] = []
        for side in (1, -1):
            for level in range(depth):
                price = ref[side] - side * (level + 1) * tick
                d = level_size(side, price)
                rate = cfg.add_rate * math.exp(-cfg.add_decay * level)
                rate *= ((d + 1) / cfg.d0) ** cfg.join_elasticity
                channels.append((EventType.ADD, side, price, rate))
            side_orders = sum(len(q) for q in books[side].values())
            for price, queue in books[side].items():
                if queue and side_orders > 1:  # never cancel a side's last order
                    d = sum(o[1] for o in queue)
                    per_order = cfg.cancel_rate * (d / cfg.d0) ** (cfg.cancel_elasticity - 1)
                    channels.append((EventType.DELETE, side, price, per_order * len(queue)))
        channels.append((EventType.EXECUTE, 0, 0, cfg.market_rate))
        rates = np.array([c[3] for c in channels])
        total = float(rates.sum())
        wait = float(rng.exponential(1 / total))
        fundamental += cfg.fundamental_vol * tick * math.sqrt(wait) * float(rng.standard_normal())
        t += wait
        if t >= horizon:
            break
        ts = start_ns + int(t * 1e9)
        kind, side, price, _ = channels[int(rng.choice(len(channels), p=rates / total))]
        if kind == EventType.ADD:
            size = _geometric(rng, cfg.mean_order_size)
            books[side].setdefault(price, deque()).append([next_id, size])
            rows.append((ts, EventType.ADD, next_id, side, price, size))
            next_id += 1
            snaps.append(snapshot())
        elif kind == EventType.DELETE:
            queue = books[side][price]
            index = int(rng.integers(len(queue)))
            oid, size = queue[index]
            del queue[index]
            rows.append((ts, EventType.DELETE, oid, side, price, size))
            snaps.append(snapshot())
        else:
            mid = (bb + ba) / 2 if bb is not None and ba is not None else fundamental
            lean = cfg.informed_weight * math.tanh((fundamental - mid) / tick)
            aggressor_buys = rng.random() < 0.5 + lean
            passive = -1 if aggressor_buys else 1
            # Never exhaust a side: real books keep a far-touch backstop.
            side_depth = sum(o[1] for q in books[passive].values() for o in q)
            remaining = min(_geometric(rng, cfg.mean_market_size), side_depth - 1)
            while remaining > 0:
                touch = best(passive)
                if touch is None:
                    break
                queue = books[passive][touch]
                order = queue[0]
                take = min(order[1], remaining)
                order[1] -= take
                remaining -= take
                rows.append((ts, EventType.EXECUTE, order[0], passive, touch, take))
                if order[1] == 0:
                    queue.popleft()
                snaps.append(snapshot())
    arr = np.array(rows, dtype=np.int64).reshape(-1, 6)
    snap = [np.array([s[i] for s in snaps], dtype=np.int64) for i in range(4)]
    return ReplaySession(
        session_id=session_id,
        symbol=symbol,
        tick=tick,
        start_ns=start_ns,
        end_ns=start_ns + int(horizon * 1e9),
        ts_ns=arr[:, 0].copy(),
        event_type=arr[:, 1].copy(),
        order_id=arr[:, 2].copy(),
        side=arr[:, 3].copy(),
        price=arr[:, 4].copy(),
        size=arr[:, 5].copy(),
        bid_px=snap[0],
        bid_sz=snap[1],
        ask_px=snap[2],
        ask_sz=snap[3],
    )
