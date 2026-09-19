"""Canonical contracts. Prices are integer source quanta; metadata defines scale.

LOBSTER uses 1/10000 USD quanta so sub-cent executions remain exact. This is
distinct from a venue's allowable quote increment. No pricing strategy is here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class Side(IntEnum):
    BID = 1
    ASK = -1


class EventType(IntEnum):
    ADD = 1
    CANCEL = 2
    DELETE = 3
    EXECUTE = 4
    EXECUTE_HIDDEN = 5
    CROSS = 6
    HALT = 7


class HaltStatus(IntEnum):
    HALTED = -1
    QUOTING = 0
    TRADING = 1


@dataclass(frozen=True, slots=True)
class LOBEvent:
    ts_ns: int
    event_type: EventType
    order_id: int
    side: Side
    price_ticks: int | None
    size: int
    halt_status: HaltStatus | None = None
    source_time_seconds: str | None = None
    timestamp_adjustment_ns: str = "0"


@dataclass(frozen=True, slots=True)
class BookSnapshot:
    ts_ns: int
    bid_px_ticks: NDArray[np.int64]
    bid_sz: NDArray[np.int64]
    ask_px_ticks: NDArray[np.int64]
    ask_sz: NDArray[np.int64]
    level_capacity: int = 0  # Requested depth; zero means unspecified by caller.

    @property
    def mid(self) -> float:
        if not len(self.bid_px_ticks) or not len(self.ask_px_ticks):
            raise ValueError("mid undefined for an empty side")
        return (int(self.bid_px_ticks[0]) + int(self.ask_px_ticks[0])) / 2

    @property
    def microprice(self) -> float:
        if not len(self.bid_px_ticks) or not len(self.ask_px_ticks):
            raise ValueError("microprice undefined for an empty side")
        bid, ask = int(self.bid_sz[0]), int(self.ask_sz[0])
        return (int(self.ask_px_ticks[0]) * bid + int(self.bid_px_ticks[0]) * ask) / (bid + ask)

    @property
    def spread_ticks(self) -> int:
        if not len(self.bid_px_ticks) or not len(self.ask_px_ticks):
            raise ValueError("spread undefined for an empty side")
        return int(self.ask_px_ticks[0]) - int(self.bid_px_ticks[0])


@dataclass(frozen=True, slots=True)
class RegimeTag:
    spread: int | None = None
    volatility: int | None = None
    depth: int | None = None


@dataclass(frozen=True, slots=True)
class MarketState:
    ts_ns: int
    book: BookSnapshot
    sigma_hat: float
    imbalance: float
    time_remaining: float
    inventory: int
    cash: float
    regime: RegimeTag


@dataclass(frozen=True, slots=True)
class Quote:
    ts_ns: int
    bid_px_ticks: int | None
    bid_size: int
    ask_px_ticks: int | None
    ask_size: int


@dataclass(frozen=True, slots=True)
class Fill:
    ts_ns: int
    side: Side
    price_ticks: int
    size: int
    queue_pos_at_entry: int
    queue_pos_at_fill: int
    mid_at_fill: float
    is_bounded_estimate: bool


@dataclass(frozen=True, slots=True)
class OwnOrderState:
    order_id: int
    side: Side
    price_ticks: int
    size_remaining: int
    queue_ahead: int
    entry_ts_ns: int


@dataclass(frozen=True, slots=True)
class EpisodeContext:
    session_id: str
    config: Mapping[str, object]
    rng: np.random.Generator


@dataclass(frozen=True, slots=True)
class LevelContext:
    side: Side
    price_ticks: int
    state: MarketState
    queue_age_ns: int


@dataclass(frozen=True, slots=True)
class IntensityAdjustment:
    join_multiplier: float
    cancel_multiplier: float
