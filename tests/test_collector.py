import json
from pathlib import Path

import polars as pl
import pytest

from asaudit.data.crypto_l3 import FullChannelRecorder, ParquetJournal, SequenceGap, iso_to_ns


def snapshot(seq: int = 100) -> dict[str, object]:
    return {"sequence": seq, "bids": [["100", "1", "bid-id"]], "asks": [["101", "2", "ask-id"]]}


def message(seq: int, kind: str = "received") -> dict[str, object]:
    return {
        "sequence": seq,
        "type": kind,
        "product_id": "BTC-USD",
        "time": "2026-09-18T00:00:00.123456789Z",
    }


def test_iso_nanoseconds_not_rounded() -> None:
    assert iso_to_ns("1970-01-01T00:00:00.123456789Z") == 123456789


def test_buffered_snapshot_overlap_then_gap_is_recorded(tmp_path: Path) -> None:
    sink = ParquetJournal(tmp_path, "BTC-USD", batch_size=2)
    rec = FullChannelRecorder("BTC-USD", sink)
    rec.start(snapshot(), 1000)
    assert rec.accept(message(99), 1001) is False
    assert rec.accept(message(100), 1002) is False
    assert rec.accept(message(101), 1003) is True
    with pytest.raises(SequenceGap):
        rec.accept(message(103), 1004)
    rec.close("sequence_gap", 1005)
    rows = pl.read_parquet(list(tmp_path.rglob("*.parquet"))).to_dicts()
    assert sum(row["kind"] == "gap" for row in rows) == 1
    assert sum(row["kind"] == "message" for row in rows) == 1
    assert all(
        "symbol=BTC-USD" in str(p) and "hour=" in str(p) for p in tmp_path.rglob("*.parquet")
    )
    end = next(json.loads(row["payload"]) for row in rows if row["kind"] == "segment_end")
    assert end["gap_free"] is False


def test_reconnect_has_new_snapshot_and_explicit_discontinuity(tmp_path: Path) -> None:
    sink = ParquetJournal(tmp_path, "BTC-USD", batch_size=100)
    rec = FullChannelRecorder("BTC-USD", sink)
    rec.start(snapshot(), 1000)
    rec.accept(message(101), 1001)
    rec.close("disconnect", 1002)
    rec.start(snapshot(200), 1003)
    rec.accept(message(201), 1004)
    rec.close("completed", 1005)
    rows = pl.read_parquet(list(tmp_path.rglob("*.parquet"))).to_dicts()
    assert len({r["segment_id"] for r in rows}) == 2
    assert sum(r["kind"] == "snapshot" for r in rows) == 2
    ends = [json.loads(r["payload"]) for r in rows if r["kind"] == "segment_end"]
    assert any(e["reason"] == "disconnect" and not e["gap_free"] for e in ends)


def test_repeated_sequence_after_snapshot_is_not_silently_dropped(tmp_path: Path) -> None:
    rec = FullChannelRecorder("BTC-USD", ParquetJournal(tmp_path, "BTC-USD"))
    rec.start(snapshot(), 0)
    rec.accept(message(101), 1)
    with pytest.raises(SequenceGap):
        rec.accept(message(101), 2)


def test_old_sequence_after_stream_has_advanced_is_not_snapshot_overlap(tmp_path: Path) -> None:
    rec = FullChannelRecorder("BTC-USD", ParquetJournal(tmp_path, "BTC-USD"))
    rec.start(snapshot(), 0)
    rec.accept(message(101), 1)
    with pytest.raises(SequenceGap):
        rec.accept(message(99), 2)


def test_second_process_does_not_overwrite_committed_chunks(tmp_path: Path) -> None:
    for _ in range(2):
        rec = FullChannelRecorder("BTC-USD", ParquetJournal(tmp_path, "BTC-USD"))
        rec.start(snapshot(), 1)
        rec.accept(message(101), 2)
        rec.close("completed", 3)
    rows = pl.read_parquet(list(tmp_path.rglob("*.parquet"))).to_dicts()
    assert len(rows) == 6
    assert len({r["segment_id"] for r in rows}) == 2
