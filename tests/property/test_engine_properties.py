"""PRD M2 property tests on replayed synthetic L3 flow (fixture data)."""

import numpy as np
from fixtures import calibration, session
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from asaudit.attribution.grid import ALL_CONFIGS, GridConfig, build_models
from asaudit.sim.competition.frozen import FrozenBook
from asaudit.sim.engine import Engine, EngineConfig, EpisodeResult, ReplaySource
from asaudit.sim.fills.base import StepContext
from asaudit.sim.fills.queue import QueueFillModel
from asaudit.strategy.avellaneda_stoikov import ASQuoter
from asaudit.strategy.symmetric import SymmetricQuoter
from asaudit.types import Side

POLICIES = ("pessimistic", "uniform", "optimistic")
SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def run(
    g: GridConfig, policy: str, seed: int, latency_ns: int, half: float, quoter: str = "symmetric"
) -> EpisodeResult:
    s = session(seed % 5 + 10, 60.0)
    cal = calibration()
    fill, info, comp = build_models(g, cal, policy)  # type: ignore[arg-type]
    engine = Engine(EngineConfig(latency_ns=latency_ns, max_inventory=15), fill, info, comp)
    q = (
        SymmetricQuoter(half, s.tick)
        if quoter == "symmetric"
        else ASQuoter(1e-4, cal.sigma, cal.intensity.k, 60.0, s.tick)
    )
    return engine.run(
        ReplaySource(s, 100_000_000, s.start_ns, s.end_ns),
        q,
        np.random.default_rng(seed),
        s.session_id,
    )


cases = st.tuples(
    st.sampled_from(ALL_CONFIGS),
    st.sampled_from(POLICIES),
    st.integers(0, 10**6),
    st.sampled_from([0, 100_000, 1_000_000, 150_000_000]),
    st.sampled_from([0.5, 1.5, 3.0]),
    st.sampled_from(["symmetric", "as"]),
)


@SETTINGS
@given(cases)
def test_accounting_inventory_and_no_through_fills(case):
    g, policy, seed, latency, half, quoter = case
    r = run(g, policy, seed, latency, half, quoter)
    s = session(seed % 5 + 10, 60.0)
    # Inventory equals the signed sum of fills.
    assert r.inventory == sum(int(f.side) * f.size for f in r.fills)
    # cash + q * mid - charges equals the decomposition at every step (checked
    # inside the ledger); rebuild the final value independently from fills.
    cash = -sum(int(f.side) * f.price_ticks * f.size for f in r.fills)
    final_mid = s.mid(s.rows_before(s.end_ns))
    assert abs(cash + r.inventory * final_mid - r.charges - r.pnl) < 1e-6
    assert r.max_identity_error < 1e-6
    # No fill at a price through the opposite touch, in the book before the fill.
    for f in r.fills:
        row = s.rows_before(f.ts_ns + 1) - 1 if f.is_bounded_estimate else s.rows_before(f.ts_ns)
        if f.side is Side.BID:
            assert f.price_ticks < s.ask_px[row, 0]
        else:
            assert f.price_ticks > s.bid_px[row, 0]


@SETTINGS
@given(st.integers(0, 10**6), st.sampled_from(POLICIES), st.integers(0, 2), st.integers(1, 30))
def test_queue_ahead_never_increases_without_reprice(seed, policy, level, size):
    s = session(seed % 5 + 10, 60.0)
    rng = np.random.default_rng(seed)
    model = QueueFillModel(policy)  # type: ignore[arg-type]
    t0 = s.start_ns + int(rng.integers(0, 30)) * 1_000_000_000
    lo = s.rows_before(t0)
    side = Side.BID if seed % 2 else Side.ASK
    px = (s.bid_px if side is Side.BID else s.ask_px)[lo, level]
    ctx = StepContext(t0, t0, s.mid(lo), s, lo, lo, FrozenBook())
    order = model.place(1, side, int(px), size, ctx)
    assert order.queue_ahead == s.level_depth(lo, int(side), int(px))
    orders = {1: order}
    t = t0
    for _ in range(40):
        lo, hi = s.rows_before(t), s.rows_before(t + 250_000_000)
        before = orders.get(1)
        fills, orders = model.step(
            orders, StepContext(t, t + 250_000_000, s.mid(lo), s, lo, hi, FrozenBook()), rng
        )
        after = orders.get(1)
        if before is not None and after is not None:
            assert after.queue_ahead <= before.queue_ahead
        for f in fills:
            assert f.queue_pos_at_fill <= f.queue_pos_at_entry
        t += 250_000_000
        if not orders:
            break


def test_reprice_goes_to_back_of_nonempty_level():
    s = session(11, 60.0)
    model = QueueFillModel("optimistic")
    row = s.rows_before(s.start_ns + 30_000_000_000)
    ctx = StepContext(s.start_ns, s.start_ns, s.mid(row), s, row, row, FrozenBook())
    front = model.place(1, Side.BID, int(s.bid_px[row, 1]), 1, ctx)
    at_touch = model.place(2, Side.BID, int(s.bid_px[row, 0]), 1, ctx)
    assert at_touch.queue_ahead == s.bid_sz[row, 0] > 0
    assert front.queue_ahead == s.bid_sz[row, 1] > 0
    improving = model.place(3, Side.BID, int(s.bid_px[row, 0]) + s.tick, 1, ctx)
    if improving.price_ticks < s.ask_px[row, 0]:
        assert improving.queue_ahead == 0


@settings(max_examples=10, deadline=None)
@given(st.integers(0, 10**6), st.sampled_from([0.5, 1.5]), st.booleans(), st.booleans())
def test_cancel_attribution_bounds_are_ordered(seed, half, a2, a3):
    # Inventory-independent quotes and no inventory cap binding keep placements
    # identical across policies, so the bound ordering must hold pathwise.
    counts = [
        sum(f.size for f in run(GridConfig(True, a2, a3), p, seed, 0, half).fills) for p in POLICIES
    ]
    assert counts[0] <= counts[1] <= counts[2]
