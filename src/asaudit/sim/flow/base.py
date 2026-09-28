"""Information-model contract (A2).

The engine values each fill at ``mid_after``; the difference from the observed
mid is booked as an adverse-selection charge, side * (observed - effective).
A2 is defined as a target level of adverse selection minus what the fill model
already embeds, so all four (A1, A2) cells stay coherent (DECISIONS 2026-09-28).
"""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from asaudit.types import Fill


@dataclass(frozen=True, slots=True)
class FillFeatures:
    spread_ticks: int
    imbalance: float  # top-of-book imbalance signed toward our side, in [-1, 1]


class AdverseModel(Protocol):
    def beta(self, f: Fill, features: FillFeatures) -> float:
        """Expected adverse mid move after the fill, price quanta, positive = against us."""
        ...


class InformationModel(Protocol):
    name: str

    def mid_after(
        self,
        f: Fill,
        horizon_ns: int,
        observed_mid: float,
        rng: np.random.Generator,
        features: FillFeatures,
    ) -> float: ...
