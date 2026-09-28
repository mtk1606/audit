"""A2 off: fills are informationally neutral.

With flow-independent (Poisson) fills nothing needs removing. With queue fills
on real flow, the calibrated expected adverse move is credited back so the fill
is valued as if neutral.
"""

import numpy as np

from asaudit.sim.flow.base import AdverseModel, FillFeatures
from asaudit.types import Fill


class NeutralFlow:
    name = "neutral"

    def __init__(self, remove_embedded: AdverseModel | None = None) -> None:
        self.remove_embedded = remove_embedded

    def mid_after(
        self,
        f: Fill,
        horizon_ns: int,
        observed_mid: float,
        rng: np.random.Generator,
        features: FillFeatures,
    ) -> float:
        if self.remove_embedded is None:
            return observed_mid
        return observed_mid + int(f.side) * self.remove_embedded.beta(f, features)
