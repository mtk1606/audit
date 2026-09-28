"""LOBSTER message + orderbook pair -> ReplaySession.

LOBSTER supplies the book after every message, so no reconstruction is needed
for replay. The state before the first message is not in the files; the first
message is therefore consumed as the initial state and replay starts after it.
HALT rows keep their type with price 0 and leave the book unchanged.
"""

import csv
from pathlib import Path

import numpy as np

from asaudit.data.lobster import SessionMetadata, parse_event, parse_snapshot, session_midnight_ns
from asaudit.sim.session import ReplaySession


def load_lobster_session(
    messages: Path,
    books: Path,
    metadata: SessionMetadata,
    tick: int = 100,
) -> ReplaySession:
    """``tick`` is $0.01 in LOBSTER's 1e-4 quanta. The session spans the first
    message's timestamp to one nanosecond after the last; episode windows are
    chosen by the caller."""
    midnight = session_midnight_ns(metadata.date, metadata.timezone)
    rows: list[tuple[int, int, int, int, int, int]] = []
    snaps: list[list[int]] = []
    with messages.open(newline="") as m, books.open(newline="") as b:
        for msg, book in zip(csv.reader(m), csv.reader(b), strict=True):
            e = parse_event(msg, metadata, midnight_ns=midnight)
            snap = parse_snapshot(book, e.ts_ns, metadata.depth)
            flat: list[int] = []
            for px, sz in ((snap.bid_px_ticks, snap.bid_sz), (snap.ask_px_ticks, snap.ask_sz)):
                pad = metadata.depth - len(px)
                flat += list(map(int, px)) + [0] * pad + list(map(int, sz)) + [0] * pad
            rows.append(
                (e.ts_ns, int(e.event_type), e.order_id, int(e.side), e.price_ticks or 0, e.size)
            )
            snaps.append(flat)
    if len(rows) < 2:
        raise ValueError("session too short")
    arr = np.asarray(rows[1:], dtype=np.int64)
    book_arr = np.asarray(snaps, dtype=np.int64)
    k = metadata.depth
    return ReplaySession(
        f"{metadata.symbol}/{metadata.date.isoformat()}",
        metadata.symbol,
        tick,
        int(rows[0][0]),
        int(arr[-1, 0]) + 1,
        arr[:, 0].copy(),
        arr[:, 1].copy(),
        arr[:, 2].copy(),
        arr[:, 3].copy(),
        arr[:, 4].copy(),
        arr[:, 5].copy(),
        book_arr[:, 0:k].copy(),
        book_arr[:, k : 2 * k].copy(),
        book_arr[:, 2 * k : 3 * k].copy(),
        book_arr[:, 3 * k : 4 * k].copy(),
    )
