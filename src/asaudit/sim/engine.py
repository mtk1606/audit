"""Event-driven ablation engine (PRD M2).

Per step [t, t + batch):
  1. build MarketState from the book valid at t (events strictly before t);
  2. ask the quoter; enforce inventory cap and post-only prices;
  3. schedule the quote to take effect at t + latency;
  4. advance own orders through the fill model, split at any activation time;
     a repriced order is re-placed at the BACK of its new level;
  5. value each fill through the information model, book any charge;
  6. mark to the mid at the end of the step and check the accounting identity.
Competition enters inside the fill model (it scales cancels ahead of us).
"""

import math
from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from asaudit.sim.accounting import Ledger
from asaudit.sim.competition.base import CompetitionModel
from asaudit.sim.fills.base import FillModel, StepContext
from asaudit.sim.fills.queue import UnobservableQueue
from asaudit.sim.flow.base import FillFeatures, InformationModel
from asaudit.sim.session import ReplaySession
from asaudit.strategy.base import Quoter
from asaudit.types import EpisodeContext, Fill, MarketState, OwnOrderState, Quote, RegimeTag, Side


class EngineConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    latency_ns: int = Field(default=0, ge=0)
    quote_size: int = Field(default=1, ge=1)
    max_inventory: int = Field(default=10**9, ge=1)
    markout_horizon_ns: int = Field(default=1_000_000_000, ge=0)
    sigma_window: int = Field(default=50, ge=2)
    identity_tolerance: float = Field(default=1e-9, gt=0)


@dataclass(frozen=True, slots=True)
class MarketStep:
    ts_ns: int
    end_ns: int
    mid: float
    next_mid: float
    row_lo: int
    row_hi: int


class MarketSource(Protocol):
    session: ReplaySession | None
    start_ns: int
    end_ns: int

    def steps(self) -> Iterator[MarketStep]: ...


class BinaryMidSource:
    """Book-free M1 source: mid moves +/- sigma*sqrt(dt) after each step's fills."""

    session: ReplaySession | None = None

    def __init__(
        self, s0: float, sigma: float, dt_ns: int, n_steps: int, rng: np.random.Generator
    ) -> None:
        self.start_ns, self.end_ns = 0, dt_ns * n_steps
        self.dt_ns, self.n_steps = dt_ns, n_steps
        jump = sigma * math.sqrt(dt_ns / 1e9)
        moves = np.where(rng.random(n_steps) < 0.5, -jump, jump)
        self.mids = s0 + np.concatenate([[0.0], np.cumsum(moves)])

    def steps(self) -> Iterator[MarketStep]:
        for i in range(self.n_steps):
            t = i * self.dt_ns
            yield MarketStep(t, t + self.dt_ns, float(self.mids[i]), float(self.mids[i + 1]), 0, 0)


class ReplaySource:
    """Batches of replayed events over [start_ns, end_ns)."""

    def __init__(self, session: ReplaySession, batch_ns: int, start_ns: int, end_ns: int) -> None:
        if batch_ns <= 0 or end_ns <= start_ns:
            raise ValueError("invalid replay window")
        if start_ns < session.start_ns or end_ns > session.end_ns:
            raise ValueError("replay window outside session")
        self.session = session
        self.batch_ns, self.start_ns, self.end_ns = batch_ns, start_ns, end_ns

    def steps(self) -> Iterator[MarketStep]:
        s = self.session
        assert s is not None
        t = self.start_ns
        while t < self.end_ns:
            end = min(t + self.batch_ns, self.end_ns)
            lo, hi = s.rows_before(t), s.rows_before(end)
            yield MarketStep(t, end, s.mid(lo), s.mid(hi), lo, hi)
            t = end


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    pnl: float
    inventory: int
    n_fills: int
    notional: float
    charges: float
    spread_capture: float
    inventory_pnl: float
    max_identity_error: float
    fills: tuple[Fill, ...]
    pnl_path: NDArray[np.float64]
    inventory_path: NDArray[np.int64]
    inventory_cap_hits: int
    n_steps: int
    withheld_quotes: int


def _features(session: ReplaySession | None, row: int, side: Side) -> FillFeatures:
    if session is None:
        return FillFeatures(0, 0.0)
    b, a = int(session.bid_sz[row, 0]), int(session.ask_sz[row, 0])
    spread = (int(session.ask_px[row, 0]) - int(session.bid_px[row, 0])) // session.tick
    imbalance = (b - a) / (b + a) if b + a else 0.0
    return FillFeatures(spread, imbalance * int(side))


class Engine:
    def __init__(
        self,
        cfg: EngineConfig,
        fill_model: FillModel,
        info_model: InformationModel,
        competition: CompetitionModel,
    ) -> None:
        self.cfg, self.fill_model, self.info_model = cfg, fill_model, info_model
        self.competition = competition

    def _desired(self, quote: Quote | None, state: MarketState, tick: int) -> dict[Side, int]:
        if quote is None:
            return {}
        out: dict[Side, int] = {}
        size = self.cfg.quote_size
        book = state.book
        for side, px in ((Side.BID, quote.bid_px_ticks), (Side.ASK, quote.ask_px_ticks)):
            if px is None:
                continue
            if side is Side.BID and state.inventory + size > self.cfg.max_inventory:
                continue
            if side is Side.ASK and state.inventory - size < -self.cfg.max_inventory:
                continue
            if book is not None and len(book.bid_px_ticks) and len(book.ask_px_ticks):
                # Post-only: never rest at or through the opposite touch.
                if side is Side.BID:
                    px = min(px, int(book.ask_px_ticks[0]) - tick)
                else:
                    px = max(px, int(book.bid_px_ticks[0]) + tick)
            out[side] = px
        return out

    def run(
        self, source: MarketSource, quoter: Quoter, rng: np.random.Generator, session_id: str
    ) -> EpisodeResult:
        cfg, s = self.cfg, source.session
        tick = s.tick if s is not None else 1
        horizon_ns = source.end_ns - source.start_ns
        quoter.reset(EpisodeContext(session_id, {"horizon_ns": horizon_ns}, rng))
        ledger = Ledger()
        orders: dict[int, OwnOrderState] = {}
        pending: deque[tuple[int, dict[Side, int]]] = deque()
        next_id = 1
        fills: list[Fill] = []
        pnl_path: list[float] = []
        inv_path: list[int] = []
        mids: deque[float] = deque(maxlen=cfg.sigma_window + 1)
        cap_hits, n_steps, started, withheld = 0, 0, False, 0
        dt_hint = 0.0
        for step in source.steps():
            n_steps += 1
            if not started:
                ledger.start(step.mid)
                started = True
            mids.append(step.mid)
            dt_hint = (step.end_ns - step.ts_ns) / 1e9
            sigma_hat = 0.0
            if len(mids) > 2 and dt_hint > 0:
                diffs = np.diff(np.asarray(mids))
                sigma_hat = float(np.std(diffs) / math.sqrt(dt_hint))
            book = s.book(step.row_lo, step.ts_ns) if s is not None else None
            imbalance = 0.0
            if book is not None and len(book.bid_sz) and len(book.ask_sz):
                b, a = int(book.bid_sz[0]), int(book.ask_sz[0])
                imbalance = (b - a) / (b + a)
            state = MarketState(
                step.ts_ns,
                step.mid,
                book,
                sigma_hat,
                imbalance,
                (source.end_ns - step.ts_ns) / horizon_ns,
                ledger.inventory,
                ledger.cash,
                RegimeTag(),
            )
            if abs(ledger.inventory) >= cfg.max_inventory:
                cap_hits += 1
            desired = self._desired(quoter.on_market_update(state), state, tick)
            if not all(math.isfinite(p) for p in desired.values()):
                raise ArithmeticError("non-finite quote")
            pending.append((step.ts_ns + cfg.latency_ns, desired))
            t, row = step.ts_ns, step.row_lo
            while True:
                activation = pending[0][0] if pending else None
                seg_end = (
                    step.end_ns
                    if activation is None or activation >= step.end_ns
                    else max(activation, t)
                )
                seg_row = s.rows_before(seg_end) if s is not None else row
                if seg_end > t or seg_row > row:
                    ctx = StepContext(t, seg_end, step.mid, s, row, seg_row, self.competition)
                    new_fills, orders = self.fill_model.step(orders, ctx, rng)
                    for f in new_fills:
                        frow = s.rows_before(f.ts_ns) if s is not None else 0
                        features = _features(s, frow, f.side)
                        effective = self.info_model.mid_after(
                            f, cfg.markout_horizon_ns, f.mid_at_fill, rng, features
                        )
                        charge = int(f.side) * (f.mid_at_fill - effective) * f.size
                        ledger.apply_fill(f, charge)
                        fills.append(f)
                        quoter.on_fill(f, state)
                    t, row = seg_end, seg_row
                if activation is None or activation >= step.end_ns:
                    break
                _, target = pending.popleft()
                ctx = StepContext(t, step.end_ns, step.mid, s, row, row, self.competition)
                current = {o.side: (oid, o) for oid, o in orders.items()}
                for side in (Side.BID, Side.ASK):
                    existing = current.get(side)
                    price = target.get(side)
                    if existing is not None and (price is None or existing[1].price_ticks != price):
                        del orders[existing[0]]
                    if price is not None and (existing is None or existing[1].price_ticks != price):
                        # Reprice: a new order at the back of the new level's queue.
                        try:
                            orders[next_id] = self.fill_model.place(
                                next_id, side, price, cfg.quote_size, ctx
                            )
                        except UnobservableQueue:
                            withheld += 1  # counted and reported, never silently placed
                        next_id += 1
            pnl_path.append(ledger.mark(step.next_mid, cfg.identity_tolerance))
            inv_path.append(ledger.inventory)
        if n_steps == 0:
            raise ValueError("empty market source")
        return EpisodeResult(
            pnl=pnl_path[-1],
            inventory=ledger.inventory,
            n_fills=ledger.n_fills,
            notional=ledger.notional,
            charges=ledger.charges,
            spread_capture=ledger.spread_capture,
            inventory_pnl=ledger.inventory_pnl,
            max_identity_error=ledger.max_identity_error,
            fills=tuple(fills),
            pnl_path=np.asarray(pnl_path),
            inventory_path=np.asarray(inv_path, dtype=np.int64),
            inventory_cap_hits=cap_hits,
            n_steps=n_steps,
            withheld_quotes=withheld,
        )


def replay_features(session: ReplaySession, rows: Sequence[int]) -> list[FillFeatures]:
    """Exposed for calibration code that must share the engine's feature definition."""
    return [_features(session, r, Side.BID) for r in rows]
