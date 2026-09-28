"""Minimal third-party submission: any object satisfying asaudit.strategy.base.Quoter.

Run it against the benchmark with:
    uv run asaudit benchmark --quoter benchmarks.example_quoter:make --config configs/ablation/fixture.toml
"""

import math

from asaudit.types import EpisodeContext, Fill, MarketState, Quote


class TwoTickQuoter:
    name = "two_tick_example"

    def __init__(self, tick: int) -> None:
        self.tick = tick

    def reset(self, ctx: EpisodeContext) -> None:
        return None

    def on_market_update(self, s: MarketState) -> Quote:
        bid = math.floor((s.mid - 2 * self.tick) / self.tick) * self.tick
        ask = math.ceil((s.mid + 2 * self.tick) / self.tick) * self.tick
        return Quote(s.ts_ns, int(bid), 1, int(ask), 1)

    def on_fill(self, f: Fill, s: MarketState) -> None:
        return None


def make(tick: int) -> TwoTickQuoter:
    return TwoTickQuoter(tick)
