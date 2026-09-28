"""Columnar replay session: events plus the level-K book after each event.

Row 0 of each book array is the state before the first event; row i + 1 is the
state after event i. Absent levels carry price 0 and size 0. Prices are integer
source quanta; ``tick`` is the venue quote increment in the same quanta.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asaudit.types import BookSnapshot

IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class ReplaySession:
    session_id: str
    symbol: str
    tick: int
    start_ns: int
    end_ns: int
    ts_ns: IntArray
    event_type: IntArray
    order_id: IntArray
    side: IntArray
    price: IntArray
    size: IntArray
    bid_px: IntArray
    bid_sz: IntArray
    ask_px: IntArray
    ask_sz: IntArray

    def __post_init__(self) -> None:
        n = len(self.ts_ns)
        for name in ("event_type", "order_id", "side", "price", "size"):
            if len(getattr(self, name)) != n:
                raise ValueError(f"{name} length differs from ts_ns")
        for name in ("bid_px", "bid_sz", "ask_px", "ask_sz"):
            arr = getattr(self, name)
            if arr.ndim != 2 or arr.shape[0] != n + 1:
                raise ValueError(f"{name} must have n_events + 1 rows")
        if n and (np.diff(self.ts_ns) < 0).any():
            raise ValueError("event timestamps are not monotone")
        if n and (self.ts_ns[0] < self.start_ns or self.ts_ns[-1] > self.end_ns):
            raise ValueError("events outside session bounds")
        if self.tick <= 0:
            raise ValueError("tick must be positive")
        for name in (
            "ts_ns",
            "event_type",
            "order_id",
            "side",
            "price",
            "size",
            "bid_px",
            "bid_sz",
            "ask_px",
            "ask_sz",
        ):
            getattr(self, name).flags.writeable = False

    @property
    def n_events(self) -> int:
        return len(self.ts_ns)

    @property
    def depth(self) -> int:
        return int(self.bid_px.shape[1])

    def book(self, row: int, ts_ns: int) -> BookSnapshot:
        """Snapshot at book row ``row`` (0 = before the first event)."""
        bid_mask, ask_mask = self.bid_sz[row] > 0, self.ask_sz[row] > 0
        return BookSnapshot(
            ts_ns,
            self.bid_px[row][bid_mask],
            self.bid_sz[row][bid_mask],
            self.ask_px[row][ask_mask],
            self.ask_sz[row][ask_mask],
            self.depth,
        )

    def mid(self, row: int) -> float:
        if self.bid_sz[row, 0] <= 0 or self.ask_sz[row, 0] <= 0:
            raise ValueError(f"mid undefined at book row {row}: empty side")
        return (int(self.bid_px[row, 0]) + int(self.ask_px[row, 0])) / 2

    def rows_before(self, ts_ns: int) -> int:
        """Book row valid at ``ts_ns``: after every event with ts < ts_ns."""
        return int(np.searchsorted(self.ts_ns, ts_ns, side="left"))

    def level_depth(self, row: int, side: int, price: int) -> int:
        px, sz = (self.bid_px, self.bid_sz) if side == 1 else (self.ask_px, self.ask_sz)
        hit = np.nonzero((px[row] == price) & (sz[row] > 0))[0]
        return int(sz[row, hit[0]]) if len(hit) else 0

    def window(self, start_ns: int, end_ns: int, session_id: str) -> "ReplaySession":
        """Sub-session over [start_ns, end_ns); its first book row is the state at start."""
        if not self.start_ns <= start_ns < end_ns <= self.end_ns:
            raise ValueError("window outside session")
        lo, hi = self.rows_before(start_ns), self.rows_before(end_ns)
        ev = slice(lo, hi)
        bk = slice(lo, hi + 1)
        return ReplaySession(
            session_id,
            self.symbol,
            self.tick,
            start_ns,
            end_ns,
            self.ts_ns[ev].copy(),
            self.event_type[ev].copy(),
            self.order_id[ev].copy(),
            self.side[ev].copy(),
            self.price[ev].copy(),
            self.size[ev].copy(),
            self.bid_px[bk].copy(),
            self.bid_sz[bk].copy(),
            self.ask_px[bk].copy(),
            self.ask_sz[bk].copy(),
        )
