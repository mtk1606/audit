from collections.abc import Mapping, Sequence
from typing import Protocol

import numpy as np

from asaudit.types import BookSnapshot, Fill, LOBEvent, OwnOrderState


class FillModel(Protocol):
    name: str

    def step(
        self,
        own_orders: Mapping[int, OwnOrderState],
        events: Sequence[LOBEvent],
        book_before: BookSnapshot,
        rng: np.random.Generator,
    ) -> tuple[list[Fill], Mapping[int, OwnOrderState]]: ...
