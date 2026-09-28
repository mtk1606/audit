from datetime import date
from pathlib import Path

import pytest

from asaudit.data.lobster import SessionMetadata
from asaudit.data.replay import load_lobster_session


def write(tmp_path: Path, messages: list[str], books: list[str]) -> tuple[Path, Path]:
    m, b = tmp_path / "m.csv", tmp_path / "b.csv"
    m.write_text("\n".join(messages) + "\n")
    b.write_text("\n".join(books) + "\n")
    return m, b


def test_lobster_pair_becomes_replay_session(tmp_path):
    # Two levels; columns ask_px, ask_sz, bid_px, bid_sz per level.
    m, b = write(
        tmp_path,
        ["34200.0,1,1,5,1000100,-1", "34200.5,1,2,3,999900,1", "34201.0,4,2,2,999900,1"],
        [
            "1000100,5,999800,4,1000200,1,999700,2",
            "1000100,5,999900,3,1000200,1,999800,4",
            "1000100,5,999900,1,1000200,1,999800,4",
        ],
    )
    s = load_lobster_session(m, b, SessionMetadata("TEST", date(2012, 6, 21), depth=2))
    assert s.n_events == 2  # first message is consumed as the initial state
    assert s.bid_px[0, 0] == 999800 and s.bid_px[1, 0] == 999900
    assert s.bid_sz[2, 0] == 1 and s.ask_px[2, 0] == 1000100
    assert s.mid(1) == (999900 + 1000100) / 2
    assert s.level_depth(2, 1, 999900) == 1
    w = s.window(s.ts_ns[0], s.end_ns, "w")
    assert w.n_events == 2 and (w.bid_px == s.bid_px).all()


def test_misaligned_pair_fails_loudly(tmp_path):
    m, b = write(
        tmp_path,
        ["34200.0,1,1,5,1000100,-1", "34200.5,1,2,3,999900,1"],
        ["1000100,5,999800,4,1000200,1,999700,2"],
    )
    with pytest.raises(ValueError):
        load_lobster_session(m, b, SessionMetadata("TEST", date(2012, 6, 21), depth=2))
