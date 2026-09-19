from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from asaudit.data.lobster import SessionMetadata, normalize_timestamp, parse_event
from asaudit.data.quality import DataQualityError, QualityPolicy, validate_pair


@pytest.mark.parametrize(
    "raw,expected,delta",
    [
        ("36754.716797047004", 36754716797047, "-0.004"),
        ("34397.878728270996", 34397878728271, "0.004"),
        ("1.0000000005", 1000000000, "-0.5"),
        ("1.0000000015", 1000000002, "0.5"),
    ],
)
def test_decimal_half_even_and_exact_provenance(raw: str, expected: int, delta: str) -> None:
    result = normalize_timestamp(raw, "nearest_ns")
    assert result.ns == expected
    assert result.raw_seconds == raw
    assert result.adjustment_ns == delta


def test_strict_mode_still_rejects_fractional_nanoseconds() -> None:
    with pytest.raises(ValueError):
        normalize_timestamp("36754.716797047004", "strict")


def test_decimal_context_cannot_change_normalization() -> None:
    with localcontext() as ctx:
        ctx.prec = 4
        result = normalize_timestamp("36754.716797047004", "nearest_ns")
    assert result.ns == 36754716797047
    assert result.adjustment_ns == "-0.004"


@given(st.integers(0, 86399), st.integers(0, 999999999))
def test_integral_source_times_are_unchanged(seconds: int, fraction: int) -> None:
    raw = f"{seconds}.{fraction:09d}"
    value = normalize_timestamp(raw, "nearest_ns")
    assert value.ns == seconds * 10**9 + fraction
    assert value.adjustment_ns == "0"


@pytest.mark.parametrize("raw", ["NaN", "inf", "-1", "86400", "86399.9999999999"])
def test_rounding_does_not_admit_invalid_or_next_day_timestamps(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_timestamp(raw, "nearest_ns")


def test_canonical_event_preserves_raw_time_and_signed_adjustment() -> None:
    metadata = SessionMetadata("TEST", date(2012, 6, 21), timestamp_policy="nearest_ns")
    event = parse_event("36754.716797047004,1,1,10,10100,-1".split(","), metadata)
    assert event.source_time_seconds == "36754.716797047004"
    assert event.timestamp_adjustment_ns == "-0.004"


def write_pair(tmp_path: Path, times: list[str]) -> tuple[Path, Path]:
    m, b = tmp_path / "message.csv", tmp_path / "book.csv"
    m.write_text("".join(f"{t},5,1,1,10100,-1\n" for t in times))
    b.write_text("10100,10,10000,10\n" * len(times))
    return m, b


def test_report_counts_new_collisions_and_lists_every_adjustment(tmp_path: Path) -> None:
    m, b = write_pair(tmp_path, ["1.0000000001", "1.0000000002", "1.0000000002"])
    metadata = SessionMetadata("TEST", date(2012, 6, 21), depth=1, timestamp_policy="nearest_ns")
    report = validate_pair(m, b, metadata, QualityPolicy())
    assert report.normalized_timestamps == 3
    assert report.new_timestamp_collisions == 1
    assert [v.event_index for v in report.timestamp_adjustments] == [0, 1, 2]
    assert [v.raw_seconds for v in report.timestamp_adjustments] == [
        "1.0000000001",
        "1.0000000002",
        "1.0000000002",
    ]
    assert sum(Decimal(v.adjustment_ns) for v in report.timestamp_adjustments) == Decimal("-0.5")


def test_normalization_cannot_hide_a_source_clock_reversal(tmp_path: Path) -> None:
    m, b = write_pair(tmp_path, ["1.0000000002", "1.0000000001"])
    metadata = SessionMetadata("TEST", date(2012, 6, 21), depth=1, timestamp_policy="nearest_ns")
    with pytest.raises(DataQualityError, match="clock reversal"):
        validate_pair(m, b, metadata, QualityPolicy())
