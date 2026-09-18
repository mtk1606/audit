from typing import Protocol

import numpy as np

from asaudit.types import Fill


class InformationModel(Protocol):
    name: str

    def mid_after(
        self, f: Fill, horizon_ns: int, observed_mid: float, rng: np.random.Generator
    ) -> float: ...
