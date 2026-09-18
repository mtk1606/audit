"""Exact source decoding; no rounding, sorting, repair, or forward filling."""

import csv
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import NDArray

from asaudit.types import BookSnapshot, EventType, HaltStatus, LOBEvent, Side


@dataclass(frozen=True, slots=True)
class SessionMetadata:
    symbol: str
    date: date
    depth: int = 10
    price_unit: str = "0.0001"
    timezone: str = "America/New_York"


def seconds_to_ns(value: str) -> int:
    match = re.fullmatch(r"(\d+)(?:\.(\d{1,9}))?", value)
    if match is None:
        raise ValueError(f"invalid exact second timestamp: {value!r}")
    seconds = int(match[1])
    if seconds >= 86400:
        raise ValueError("timestamp outside session date")
    return seconds * 10**9 + int((match[2] or "").ljust(9, "0"))


def session_midnight_ns(day: date, tz: str = "America/New_York") -> int:
    midnight = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(tz))
    delta = midnight.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 10**9


def parse_event(
    row: Sequence[str], metadata: SessionMetadata, *, midnight_ns: int | None = None
) -> LOBEvent:
    if len(row) != 6:
        raise ValueError("expected six message fields")
    ts = (
        session_midnight_ns(metadata.date, metadata.timezone)
        if midnight_ns is None
        else midnight_ns
    )
    ts += seconds_to_ns(row[0])
    event_type = EventType(int(row[1]))
    order_id, size, price, side = int(row[2]), int(row[3]), int(row[4]), Side(int(row[5]))
    if metadata.price_unit != "0.0001":
        raise ValueError("LOBSTER source price unit must be 0.0001; conversion is not implicit")
    if order_id < 0 or size < 0:
        raise ValueError("negative order id or size")
    if event_type is EventType.HALT:
        if size != 0 or order_id != 0 or side is not Side.ASK:
            raise ValueError("invalid halt fields")
        return LOBEvent(ts, event_type, order_id, side, None, 0, HaltStatus(price))
    if price <= 0 or size <= 0:
        raise ValueError("nonpositive executable price or size")
    return LOBEvent(ts, event_type, order_id, side, price, size)


def _readonly(values: list[int]) -> NDArray[np.int64]:
    array = np.asarray(values, dtype=np.int64)
    array.flags.writeable = False
    return array


def parse_snapshot(row: Sequence[str], ts_ns: int, depth: int) -> BookSnapshot:
    if depth < 1 or len(row) != 4 * depth:
        raise ValueError("snapshot column count does not match depth")
    raw = list(map(int, row))
    sides: list[tuple[list[int], list[int]]] = []
    for offset, sentinel, descending in [(2, -9999999999, True), (0, 9999999999, False)]:
        px: list[int] = []
        sz: list[int] = []
        padding = False
        for price, size in zip(raw[offset::4], raw[offset + 1 :: 4], strict=True):
            if price == sentinel and size == 0:
                padding = True
                continue
            if padding or price <= 0 or size <= 0:
                raise ValueError("invalid level or dummy padding")
            if px and ((descending and price >= px[-1]) or (not descending and price <= px[-1])):
                raise ValueError("levels not strictly ordered")
            px.append(price)
            sz.append(size)
        sides.append((px, sz))
    return BookSnapshot(
        ts_ns,
        _readonly(sides[0][0]),
        _readonly(sides[0][1]),
        _readonly(sides[1][0]),
        _readonly(sides[1][1]),
        depth,
    )


def iter_lobster_events(path: Path, metadata: SessionMetadata) -> Iterator[LOBEvent]:
    midnight = session_midnight_ns(metadata.date, metadata.timezone)
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            yield parse_event(row, metadata, midnight_ns=midnight)
