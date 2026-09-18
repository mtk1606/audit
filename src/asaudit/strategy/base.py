from typing import Protocol

from asaudit.types import EpisodeContext, Fill, MarketState, Quote


class Quoter(Protocol):
    name: str

    def reset(self, ctx: EpisodeContext) -> None: ...

    def on_market_update(self, s: MarketState) -> Quote | None: ...

    def on_fill(self, f: Fill, s: MarketState) -> None: ...
