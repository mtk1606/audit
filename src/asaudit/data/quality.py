import csv
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from itertools import zip_longest
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from asaudit.data.lobster import SessionMetadata, parse_event, parse_snapshot, session_midnight_ns
from asaudit.sim.book import BoundedBook
from asaudit.types import EventType


class QualityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    max_gap_pct: Decimal = Field(default=Decimal("0.001"), ge=0, le=1)
    fail_on_crossed_book: bool = True


class DataQualityError(ValueError):
    def __init__(
        self, message: str, event_index: int, context: tuple[str, ...],
        report: "DataQualityReport | None" = None,
    ) -> None:
        self.event_index = event_index
        self.context = context
        self.report = report
        super().__init__(f"event_index={event_index}: {message}; context={context}")


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    rows: int
    sequence_gaps: int | None
    crossed_books: int
    zero_size_levels: int
    halts: int
    clock_reversals: int
    cross_trades: int
    supplied_initial_levels: int
    supplied_boundary_levels: int
    independently_checked_levels: int
    snapshot_assisted: bool = True
    order_identity_complete: bool = False
    sequence_check: str = "unavailable_in_lobster_message_format"


def validate_pair(
    messages: Path, snapshots: Path, metadata: SessionMetadata, policy: QualityPolicy
) -> DataQualityReport:
    rows = crossed = zero = halts = crosses = supplied = initial = checked = reversals = 0

    def report() -> DataQualityReport:
        return DataQualityReport(rows, None, crossed, zero, halts, reversals,
                                 crosses, initial, supplied, checked)
    book: BoundedBook | None = None
    previous_ts: int | None = None
    history: deque[str] = deque(maxlen=10)
    midnight = session_midnight_ns(metadata.date, metadata.timezone)
    with messages.open(newline="") as mf, snapshots.open(newline="") as sf:
        pairs = iter(zip_longest(csv.reader(mf), csv.reader(sf)))
        for index, (event_row, book_row) in enumerate(pairs):
            try:
                if event_row is None or book_row is None:
                    raise ValueError("message/snapshot row count mismatch")
                event = parse_event(event_row, metadata, midnight_ns=midnight)
                observed = parse_snapshot(book_row, event.ts_ns, metadata.depth)
                if previous_ts is not None and event.ts_ns < previous_ts:
                    reversals += 1
                    raise ValueError("clock reversal")
                previous_ts = event.ts_ns
                zero += 2 * metadata.depth - len(observed.bid_sz) - len(observed.ask_sz)
                halts += event.event_type is EventType.HALT
                crosses += event.event_type is EventType.CROSS
                if len(observed.bid_sz) and len(observed.ask_sz) and observed.spread_ticks < 0:
                    crossed += 1
                    if policy.fail_on_crossed_book:
                        raise ValueError("crossed book")
                if book is None:
                    book = BoundedBook(observed)
                    initial = len(observed.bid_sz) + len(observed.ask_sz)
                else:
                    result = book.advance(event, observed)
                    supplied += result.supplied_boundary_levels
                    checked += result.independently_checked_levels
                rows += 1
                history.append(f"{index}: {event_row}")
            except (ValueError, OverflowError) as exc:
                context = [*history, f"{index}: {event_row}"]
                for _ in range(10):
                    next_pair = next(pairs, None)
                    if next_pair is None:
                        break
                    context.append(str(next_pair[0]))
                raise DataQualityError(str(exc), index, tuple(context), report()) from exc
    if rows == 0:
        raise DataQualityError("empty session", 0, (), report())
    return report()
