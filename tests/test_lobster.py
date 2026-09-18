from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from asaudit.data.lobster import SessionMetadata, parse_event, seconds_to_ns, session_midnight_ns
from asaudit.data.quality import DataQualityError, QualityPolicy, validate_pair
from asaudit.types import EventType, HaltStatus, Side


def pair(tmp_path: Path, events: list[str], books: list[str]) -> tuple[Path, Path]:
    m, b = tmp_path / "message.csv", tmp_path / "orderbook.csv"
    m.write_text("\n".join(events) + "\n")
    b.write_text("\n".join(books) + "\n")
    return m, b


def meta(depth: int = 2) -> SessionMetadata:
    return SessionMetadata(symbol="TEST", date=date(2012, 6, 21), depth=depth)


@given(st.integers(0, 86_399), st.integers(0, 999_999_999))
def test_time_conversion_is_exact(seconds: int, fraction: int) -> None:
    assert seconds_to_ns(f"{seconds}.{fraction:09d}") == seconds * 10**9 + fraction


@pytest.mark.parametrize("bad", ["NaN", "inf", "-1", "86400", "1.0000000001"])
def test_bad_time_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        seconds_to_ns(bad)


def test_eastern_midnight_and_subcent_execution_preserved() -> None:
    assert session_midnight_ns(date(2012, 6, 21)) == 1340251200000000000
    e = parse_event("34200.000000001,5,42,10,1234550,-1".split(","), meta())
    assert e.ts_ns == 1340285400000000001
    assert e.price_ticks == 1234550
    assert meta().price_unit == "0.0001"
    assert e.side is Side.ASK


@pytest.mark.parametrize(
    "raw,status", [("-1", HaltStatus.HALTED), ("0", HaltStatus.QUOTING), ("1", HaltStatus.TRADING)]
)
def test_halt_status_is_not_an_executable_price(raw: str, status: HaltStatus) -> None:
    e = parse_event(f"34200,7,0,0,{raw},-1".split(","), meta())
    assert e.event_type is EventType.HALT
    assert e.price_ticks is None
    assert e.halt_status is status


def test_cross_event_preserved() -> None:
    e = parse_event("34200,6,0,100,1234500,1".split(","), meta())
    assert e.event_type is EventType.CROSS
    assert e.price_ticks == 1234500


def test_snapshot_boundary_is_supplied_but_retained_levels_are_checked(tmp_path: Path) -> None:
    m, b = pair(
        tmp_path,
        ["34200,1,1,5,10100,-1", "34201,3,2,10,10000,1"],
        ["10100,5,10000,10,10200,20,9900,30", "10100,5,9900,30,10200,20,9800,40"],
    )
    report = validate_pair(m, b, meta(), QualityPolicy())
    assert report.rows == 2
    assert report.supplied_initial_levels == 4
    assert report.supplied_boundary_levels == 1
    assert report.independently_checked_levels == 3
    assert report.sequence_gaps is None
    assert report.order_identity_complete is False
    assert report.snapshot_assisted is True
    # Changing a retained level must fail, even if the boundary is supplied.
    b.write_text("10100,5,10000,10,10200,20,9900,30\n10100,6,9900,30,10200,20,9800,40\n")
    with pytest.raises(DataQualityError, match="mismatch") as err:
        validate_pair(m, b, meta(), QualityPolicy())
    assert err.value.event_index == 1
    assert err.value.context


def test_interior_snapshot_injection_is_not_excused_as_boundary(tmp_path: Path) -> None:
    m, b = pair(
        tmp_path,
        ["34200,1,1,5,10100,-1", "34201,5,9,2,10100,-1"],
        ["10100,5,10000,10,10200,20,9900,30", "10050,99,10000,10,10100,5,9900,30"],
    )
    with pytest.raises(DataQualityError):
        validate_pair(m, b, meta(), QualityPolicy())


def test_new_limit_order_is_checked_not_imported(tmp_path: Path) -> None:
    m, b = pair(
        tmp_path,
        ["34200,1,1,5,10100,-1", "34201,1,9,2,10050,-1"],
        ["10100,5,10000,10,10200,20,9900,30", "10050,99,10000,10,10100,5,9900,30"],
    )
    with pytest.raises(DataQualityError, match="mismatch"):
        validate_pair(m, b, meta(), QualityPolicy())


@given(st.integers(2, 100000), st.integers(1, 1000))
def test_partial_cancel_arithmetic(size: int, remaining: int) -> None:
    from asaudit.data.lobster import parse_snapshot
    from asaudit.sim.book import BoundedBook

    before = parse_snapshot(f"10100,{size + remaining},10000,10".split(","), 0, 1)
    book = BoundedBook(before)
    e = parse_event(f"34200,2,9,{size},10100,-1".split(","), meta(1))
    after = parse_snapshot(f"10100,{remaining},10000,10".split(","), e.ts_ns, 1)
    result = book.advance(e, after)
    assert result.supplied_boundary_levels == 0
    assert result.independently_checked_levels == 2


@pytest.mark.parametrize(
    "event,book",
    [
        ("34199,1,1,1,10100,-1", "10100,6,10000,10"),
        ("34201,99,1,1,10100,-1", "10100,6,10000,10"),
        ("34201,1,1,-1,10100,-1", "10100,4,10000,10"),
        ("34201,1,1,1,10100,-1", "9900,6,10000,10"),
    ],
)
def test_bad_records_fail_loudly(tmp_path: Path, event: str, book: str) -> None:
    m, b = pair(tmp_path, ["34200,1,1,5,10100,-1", event], ["10100,5,10000,10", book])
    with pytest.raises(DataQualityError):
        validate_pair(m, b, meta(1), QualityPolicy())


def test_row_count_mismatch_and_empty_session(tmp_path: Path) -> None:
    m, b = pair(tmp_path, ["34200,1,1,5,10100,-1"], ["10100,5,10000,10", "10100,5,10000,10"])
    with pytest.raises(DataQualityError, match="row count"):
        validate_pair(m, b, meta(1), QualityPolicy())
    m.write_text("")
    b.write_text("")
    with pytest.raises(DataQualityError, match="empty"):
        validate_pair(m, b, meta(1), QualityPolicy())


def test_dummy_levels_are_counted_not_real_prices(tmp_path: Path) -> None:
    m, b = pair(tmp_path, ["34200,1,1,5,10100,-1"], ["10100,5,10000,10,9999999999,0,-9999999999,0"])
    report = validate_pair(m, b, meta(), QualityPolicy())
    assert report.zero_size_levels == 2


def test_boundary_provenance_identifies_supplied_side_price_and_size() -> None:
    from asaudit.data.lobster import parse_snapshot
    from asaudit.sim.book import BoundedBook

    initial = parse_snapshot("10100,5,10000,10,10200,20,9900,30".split(","), 0, 2)
    event = parse_event("34201,3,2,10,10000,1".split(","), meta())
    final = parse_snapshot("10100,5,9900,30,10200,20,9800,40".split(","), event.ts_ns, 2)
    result = BoundedBook(initial).advance(event, final)
    assert [(v.side, v.price_ticks, v.size) for v in result.supplied_levels] == [
        (Side.BID, 9800, 40)
    ]


def test_added_boundary_quantity_cannot_be_less_than_the_add() -> None:
    from asaudit.data.lobster import parse_snapshot
    from asaudit.sim.book import BoundedBook

    # Initial book contains fewer occupied levels than the requested capacity.
    initial = parse_snapshot("10100,5,10000,10,9999999999,0,-9999999999,0".split(","), 0, 2)
    event = parse_event("34201,1,2,50,9900,1".split(","), meta())
    final = parse_snapshot("10100,5,10000,10,9999999999,0,9900,1".split(","), event.ts_ns, 2)
    with pytest.raises(ValueError):
        BoundedBook(initial).advance(event, final)


def test_failed_session_retains_clock_reversal_count(tmp_path: Path) -> None:
    m, b = pair(
        tmp_path,
        ["34200,1,1,5,10100,-1", "34199,5,9,1,10100,-1"],
        ["10100,5,10000,10", "10100,5,10000,10"],
    )
    with pytest.raises(DataQualityError) as err:
        validate_pair(m, b, meta(1), QualityPolicy())
    assert err.value.report.clock_reversals == 1
    assert err.value.report.rows == 1
