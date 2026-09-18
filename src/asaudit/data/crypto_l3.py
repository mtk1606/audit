"""Loss-aware Coinbase full-channel capture. No live trading or order routing.

Each connection starts a new snapshot-anchored segment. Recovered book state
does not imply recovered event history. The raw feed and snapshot are retained
for later order-level reconstruction; this module does not fabricate order IDs.
"""

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
import polars as pl
import structlog
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


class SequenceGap(ValueError):
    pass


def _integer(value: object, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")
    return value


def json_object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError("expected a JSON object with string keys")
    return cast(dict[str, object], value)


def iso_to_ns(value: str) -> int:
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", value)
    if match is None:
        raise ValueError("expected UTC ISO timestamp with at most nine fractional digits")
    stamp = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    delta = stamp - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 10**9 + int((match[2] or "").ljust(9, "0"))


class ParquetJournal:
    def __init__(self, root: Path, symbol: str, batch_size: int = 1000) -> None:
        if not re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+", symbol) or batch_size < 1:
            raise ValueError("invalid product or batch size")
        self.root = root
        self.symbol = symbol
        self.batch_size = batch_size
        self.pending: list[dict[str, object]] = []
        self.paths: list[Path] = []

    def append(self, segment: str, kind: str, payload: Mapping[str, object], recv_ns: int) -> None:
        if type(recv_ns) is not int or recv_ns < 0:
            raise ValueError("receive timestamp must be nonnegative integer nanoseconds")
        stamp = payload.get("time")
        exchange_ts = iso_to_ns(stamp) if isinstance(stamp, str) else None
        sequence = payload.get("sequence")
        if sequence is not None:
            sequence = _integer(sequence, "sequence")
        self.pending.append(
            {
                "segment_id": segment,
                "kind": kind,
                "symbol": self.symbol,
                "recv_ts_ns": recv_ns,
                "exchange_ts_ns": exchange_ts,
                "sequence": sequence,
                "payload": json.dumps(
                    dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
                ),
            }
        )
        if len(self.pending) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for row in self.pending:
            stamp = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                seconds=_integer(row["recv_ts_ns"], "recv_ts_ns") // 10**9
            )
            groups[(stamp.strftime("%Y-%m-%d"), stamp.strftime("%H"))].append(row)
        schema = {
            "segment_id": pl.String,
            "kind": pl.String,
            "symbol": pl.String,
            "recv_ts_ns": pl.Int64,
            "exchange_ts_ns": pl.Int64,
            "sequence": pl.Int64,
            "payload": pl.String,
        }
        for (day, hour), rows in groups.items():
            folder = self.root / f"symbol={self.symbol}" / f"date={day}" / f"hour={hour}"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{uuid4().hex}.parquet"
            temporary = path.with_suffix(".partial")
            pl.DataFrame(rows, schema=schema).write_parquet(temporary)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            if hasattr(os, "O_DIRECTORY"):
                fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            self.paths.append(path)
        self.pending.clear()


class FullChannelRecorder:
    def __init__(self, symbol: str, journal: ParquetJournal) -> None:
        self.symbol = symbol
        self.journal = journal
        self.segment: str | None = None
        self.snapshot_sequence = 0
        self.last_sequence = 0
        self.last_exchange_ns: int | None = None
        self.gaps = 0
        self.messages = 0
        self.segments = 0
        self.discontinuities = 0
        self.segment_gaps = 0

    def start(self, snapshot: dict[str, object], recv_ns: int) -> None:
        if self.segment is not None:
            raise ValueError("previous segment must be closed")
        seq = _integer(snapshot.get("sequence"), "snapshot sequence")
        ids: set[str] = set()
        for side in ("bids", "asks"):
            levels = snapshot.get(side)
            if not isinstance(levels, list):
                raise ValueError("L3 snapshot must contain order lists")
            for level in levels:
                if not isinstance(level, list) or len(level) != 3:
                    raise ValueError("L3 snapshot must contain price, size, order id")
                price, size, order_id = level
                if not all(isinstance(x, str) for x in level):
                    raise ValueError("L3 snapshot values must be strings")
                if (
                    not isinstance(price, str)
                    or not isinstance(size, str)
                    or not isinstance(order_id, str)
                ):
                    raise ValueError("invalid snapshot field types")
                p, s = Decimal(price), Decimal(size)
                if not p.is_finite() or not s.is_finite() or p <= 0 or s <= 0:
                    raise ValueError("nonpositive or nonfinite snapshot price/size")
                if order_id in ids:
                    raise ValueError("duplicate snapshot order id")
                ids.add(order_id)
        self.segment = uuid4().hex
        self.snapshot_sequence = self.last_sequence = seq
        self.last_exchange_ns = None
        self.segment_gaps = 0
        self.segments += 1
        self.journal.append(self.segment, "snapshot", snapshot, recv_ns)
        self.journal.flush()  # A segment's anchor must survive before messages.

    def accept(self, message: dict[str, object], recv_ns: int) -> bool:
        if self.segment is None:
            raise ValueError("snapshot required before feed messages")
        if message.get("product_id") != self.symbol:
            raise ValueError("unexpected product id")
        seq = _integer(message.get("sequence"), "message sequence")
        if seq <= self.snapshot_sequence and self.last_sequence == self.snapshot_sequence:
            return False  # Buffered pre-snapshot overlap, not an arbitrary duplicate.
        if seq != self.last_sequence + 1:
            self.gaps += 1
            self.segment_gaps += 1
            self.journal.append(
                self.segment,
                "gap",
                {
                    "expected": self.last_sequence + 1,
                    "observed": seq,
                    "missing_events": max(0, seq - self.last_sequence - 1),
                },
                recv_ns,
            )
            self.journal.flush()
            raise SequenceGap(f"expected {self.last_sequence + 1}, observed {seq}")
        stamp = message.get("time")
        if not isinstance(stamp, str):
            raise ValueError("sequenced full-channel message missing time")
        ns = iso_to_ns(stamp)
        if self.last_exchange_ns is not None and ns < self.last_exchange_ns:
            raise ValueError("exchange clock reversal")
        kind = message.get("type")
        if kind not in {"received", "open", "done", "match", "change", "activate"}:
            raise ValueError(f"unknown full-channel event type: {kind!r}")
        self.journal.append(self.segment, "message", message, recv_ns)
        self.last_sequence = seq
        self.last_exchange_ns = ns
        self.messages += 1
        return True

    def close(self, reason: str, recv_ns: int) -> None:
        if self.segment is None:
            return
        if reason != "completed":
            self.discontinuities += 1
        self.journal.append(
            self.segment,
            "segment_end",
            {
                "reason": reason,
                "last_sequence": self.last_sequence,
                "gap_free": self.segment_gaps == 0 and reason == "completed",
            },
            recv_ns,
        )
        self.journal.flush()
        self.segment = None


async def capture_connection(
    recorder: FullChannelRecorder,
    snapshot_url: str,
    websocket_url: str,
    deadline: float,
    queue_capacity: int,
    flush_seconds: float,
) -> None:
    """Buffer stream before REST snapshot. Any gap aborts this segment."""
    async with connect(websocket_url, max_size=8 * 1024 * 1024, open_timeout=15) as ws:
        await ws.send(
            json.dumps(
                {"type": "subscribe", "product_ids": [recorder.symbol], "channels": ["full"]}
            )
        )
        buffer: asyncio.Queue[tuple[dict[str, object], int] | Exception] = asyncio.Queue(
            queue_capacity
        )

        async def receive() -> None:
            try:
                async for raw in ws:
                    # JSON is dynamically typed at this boundary; validate its shape.
                    obj = json_object(json.loads(raw))
                    await buffer.put((obj, time.time_ns()))
                await buffer.put(ConnectionError("websocket ended"))
            except (ConnectionClosed, OSError, ValueError) as exc:
                await buffer.put(exc)

        reader = asyncio.create_task(receive())
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(snapshot_url, params={"level": 3})
                response.raise_for_status()
                snapshot = json_object(response.json())
            recorder.start(snapshot, time.time_ns())
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                try:
                    item = await asyncio.wait_for(buffer.get(), min(flush_seconds, remaining))
                except TimeoutError:
                    recorder.journal.flush()
                    continue
                if isinstance(item, Exception):
                    raise item
                obj, received_ns = item
                if obj.get("type") == "error":
                    raise ValueError(f"exchange rejected subscription: {obj}")
                if obj.get("type") == "subscriptions":
                    continue
                recorder.accept(obj, received_ns)
            recorder.close("completed", time.time_ns())
        finally:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass  # Intentional cancellation of our own background receiver.


async def collect(
    recorder: FullChannelRecorder,
    duration_seconds: int,
    max_reconnects: int,
    reconnect_seconds: float,
    queue_capacity: int,
    flush_seconds: float,
    websocket_url: str = "wss://ws-feed.exchange.coinbase.com",
    rest_root: str = "https://api.exchange.coinbase.com",
) -> None:
    deadline = time.monotonic() + duration_seconds
    reconnects = 0
    while time.monotonic() < deadline:
        try:
            await capture_connection(
                recorder,
                f"{rest_root}/products/{recorder.symbol}/book",
                websocket_url,
                deadline,
                queue_capacity,
                flush_seconds,
            )
        except (ConnectionClosed, OSError, TimeoutError, httpx.HTTPError, SequenceGap) as exc:
            recorder.close("disconnect", time.time_ns())
            structlog.get_logger("asaudit").warning(
                "collector_reconnect", reason=str(exc), attempt=reconnects
            )
            reconnects += 1
            if reconnects > max_reconnects:
                raise
            await asyncio.sleep(min(reconnect_seconds, max(0, deadline - time.monotonic())))
        except (ValueError, asyncio.CancelledError):
            recorder.close("invalid_data_or_cancelled", time.time_ns())
            raise
        else:
            break
