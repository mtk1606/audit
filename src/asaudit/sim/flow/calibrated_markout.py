"""A2 on: fills carry the empirical conditional adverse move.

Under flow-independent fills the calibrated conditional mean is charged. Under
queue fills on replayed flow the markout is already observed, so nothing is
added. The conditional mean, not a random draw, is charged: same expectation,
lower variance, and no extra random stream to keep aligned across the grid.
"""

import numpy as np

from asaudit.sim.flow.base import AdverseModel, FillFeatures
from asaudit.types import Fill


class CalibratedMarkoutFlow:
    name = "calibrated_markout"

    def __init__(self, model: AdverseModel, embedded: bool) -> None:
        self.model, self.embedded = model, embedded

    def mid_after(
        self,
        f: Fill,
        horizon_ns: int,
        observed_mid: float,
        rng: np.random.Generator,
        features: FillFeatures,
    ) -> float:
        if self.embedded:
            return observed_mid
        return observed_mid - int(f.side) * self.model.beta(f, features)
