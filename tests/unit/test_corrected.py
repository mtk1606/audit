import math

import numpy as np
import pytest
from fixtures import calibration
from hypothesis import given, settings
from hypothesis import strategies as st

from asaudit.strategy.avellaneda_stoikov import ASParameters, quote
from asaudit.strategy.corrected import CorrectedQuoter
from asaudit.types import BookSnapshot, MarketState, RegimeTag

TICK = 100


def market(q: int, tau: float, depth: int = 10) -> MarketState:
    mid = 1_000_050.0
    bids = np.array([1_000_000 - TICK * i for i in range(depth)], dtype=np.int64)
    asks = np.array([1_000_100 + TICK * i for i in range(depth)], dtype=np.int64)
    sizes = np.full(depth, 15, dtype=np.int64)
    book = BookSnapshot(0, bids, sizes, asks, sizes, depth)
    return MarketState(0, mid, book, 50.0, 0.0, tau, q, 0.0, RegimeTag())


@settings(max_examples=40, deadline=None)
@given(st.integers(-6, 6), st.floats(0.05, 1.0))
def test_no_correction_reduces_to_as_on_the_tick_grid(q, tau):
    cal = calibration()
    gamma = 0.01 / TICK
    quoter = CorrectedQuoter(
        gamma, cal, 300.0, TICK, queue_term=False, adverse_term=False, max_levels=30
    )
    s = market(q, tau, depth=30)
    chosen = quoter.on_market_update(s)
    t = 300.0 * (1 - tau)
    ref = quote(s.mid, q, t, ASParameters(gamma, cal.sigma, cal.intensity.k, 300.0))
    # The objective is unimodal in delta: the grid argmax neighbours the AS optimum,
    # unless AS would cross the book (then the most aggressive passive price).
    lo_b, hi_b = math.floor(ref.bid / TICK) * TICK, math.ceil(ref.bid / TICK) * TICK
    assert chosen.bid_px_ticks in {min(lo_b, 1_000_000), min(hi_b, 1_000_000)}
    lo_a, hi_a = math.floor(ref.ask / TICK) * TICK, math.ceil(ref.ask / TICK) * TICK
    assert chosen.ask_px_ticks in {max(lo_a, 1_000_100), max(hi_a, 1_000_100)}


def test_adverse_term_widens_and_queue_term_is_finite():
    cal = calibration()
    gamma = 0.01 / TICK
    s = market(0, 0.5)
    plain = CorrectedQuoter(gamma, cal, 300.0, TICK, queue_term=False, adverse_term=False)
    adverse = CorrectedQuoter(gamma, cal, 300.0, TICK, queue_term=False, adverse_term=True)
    both = CorrectedQuoter(gamma, cal, 300.0, TICK)
    p, a = plain.on_market_update(s), adverse.on_market_update(s)
    assert cal.markout.overall > 0
    assert a.bid_px_ticks <= p.bid_px_ticks and a.ask_px_ticks >= p.ask_px_ticks
    b = both.on_market_update(s)
    assert b.bid_px_ticks < b.ask_px_ticks
    assert both.name == "corrected:both" and adverse.name == "corrected:adverse"


def test_inventory_skews_corrected_quotes():
    cal = calibration()
    quoter = CorrectedQuoter(0.05 / TICK, cal, 300.0, TICK)
    long, short = quoter.on_market_update(market(8, 1.0)), quoter.on_market_update(market(-8, 1.0))
    assert long.bid_px_ticks <= short.bid_px_ticks and long.ask_px_ticks <= short.ask_px_ticks


def test_rejects_nonpositive_gamma():
    with pytest.raises(ValueError):
        CorrectedQuoter(0.0, calibration(), 300.0, TICK)
