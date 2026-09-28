"""M4 corrected quoting rule: queue-conditional intensity plus informed flow.

Derivation: docs/DERIVATION_M4.draft.md. Under exponential utility and the AS
frozen-inventory approximation, each side solves

    max over delta of  lambda(delta) * (1 - exp(-gamma * (delta - c - beta))) / gamma

with c_bid = gamma*sigma^2*tau*(q + 1/2) and c_ask = gamma*sigma^2*tau*(1/2 - q),
the marginal inventory cost of one more unit. With lambda = A*exp(-k*delta),
beta = 0 and continuous delta, the maximiser is c + ln(1 + gamma/k)/gamma,
which is exactly AS. The correction:

- queue term: lambda(delta) = A*exp(-k*delta) * pi(Q(delta)), where Q(delta) is
  the queue we would join at that price and pi the fitted fill probability;
- adverse term: beta(delta) is the calibrated expected adverse move for a fill
  at that price, which reduces the value of the fill.

Prices are searched on the venue tick grid, from the most aggressive price
that stays passive out to the visible depth. Either term can be disabled for
the M4 ablation (queue only, adverse only, both).
"""

import math

from asaudit.calibration.bundle import Calibration
from asaudit.sim.flow.base import FillFeatures
from asaudit.types import EpisodeContext, Fill, MarketState, Quote, Side


class CorrectedQuoter:
    def __init__(
        self,
        gamma: float,
        cal: Calibration,
        horizon_s: float,
        tick: int,
        *,
        queue_term: bool = True,
        adverse_term: bool = True,
        max_levels: int = 10,
    ) -> None:
        if gamma <= 0:
            raise ValueError("corrected rule needs gamma > 0")
        self.gamma, self.cal, self.horizon, self.tick = gamma, cal, horizon_s, tick
        self.queue_term, self.adverse_term, self.max_levels = queue_term, adverse_term, max_levels
        suffix = {(True, True): "both", (True, False): "queue", (False, True): "adverse"}.get(
            (queue_term, adverse_term), "none"
        )
        self.name = f"corrected:{suffix}"

    def reset(self, ctx: EpisodeContext) -> None:
        return None

    def on_fill(self, f: Fill, s: MarketState) -> None:
        return None

    def _candidates(self, s: MarketState, side: Side) -> list[tuple[int, int]]:
        """(price, queue ahead if we join) on the tick grid, passive only."""
        book = s.book
        if book is None or not len(book.bid_px_ticks) or not len(book.ask_px_ticks):
            raise ValueError("corrected quoter needs a two-sided book")
        bid0, ask0 = int(book.bid_px_ticks[0]), int(book.ask_px_ticks[0])
        levels = (
            dict(zip(map(int, book.bid_px_ticks), map(int, book.bid_sz), strict=True))
            if side is Side.BID
            else dict(zip(map(int, book.ask_px_ticks), map(int, book.ask_sz), strict=True))
        )
        visible = sorted(levels, reverse=side is Side.BID)
        out: list[tuple[int, int]] = []
        start = ask0 - self.tick if side is Side.BID else bid0 + self.tick
        for j in range(self.max_levels + (ask0 - bid0) // self.tick):
            price = start - j * self.tick if side is Side.BID else start + j * self.tick
            if len(visible) == book.level_capacity and (price - visible[-1]) * int(side) < 0:
                break  # beyond visible depth: queue unobservable
            out.append((price, levels.get(price, 0)))
        return out

    def _choose(self, s: MarketState, side: Side, cost: float, features: FillFeatures) -> int:
        cal, g = self.cal, self.gamma
        book = s.book
        assert book is not None
        opposite = int(book.ask_sz[0] if side is Side.BID else book.bid_sz[0])
        wide = float(int(book.ask_px_ticks[0]) - int(book.bid_px_ticks[0]) > self.tick)
        best_price, best_value = None, -math.inf
        for price, queue in self._candidates(s, side):
            delta = int(side) * (s.mid - price)
            log_lam = math.log(cal.intensity.A) - cal.intensity.k * delta
            if self.queue_term:
                p = cal.queue_fill.probability(queue, opposite, features.imbalance, wide)
                log_lam += math.log(max(p, 1e-12))
            beta = 0.0
            if self.adverse_term:
                probe = Fill(s.ts_ns, side, price, 1, queue, queue, s.mid, True)
                beta = cal.markout.beta(probe, features)
            edge = delta - cost - beta
            value = math.exp(log_lam) * -math.expm1(-g * edge) / g
            if value > best_value:
                best_price, best_value = price, value
        if best_price is None:
            raise ValueError("no admissible quote price")
        return best_price

    def on_market_update(self, s: MarketState) -> Quote:
        tau = self.horizon * s.time_remaining
        risk = self.gamma * self.cal.sigma**2 * tau
        book = s.book
        assert book is not None
        b, a = int(book.bid_sz[0]), int(book.ask_sz[0])
        imb = (b - a) / (b + a) if b + a else 0.0
        spread = (int(book.ask_px_ticks[0]) - int(book.bid_px_ticks[0])) // self.tick
        bid = self._choose(s, Side.BID, risk * (s.inventory + 0.5), FillFeatures(spread, imb))
        ask = self._choose(s, Side.ASK, risk * (0.5 - s.inventory), FillFeatures(spread, -imb))
        return Quote(s.ts_ns, bid, 1, ask, 1)
