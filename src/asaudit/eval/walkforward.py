"""Expanding-window walk-forward (PRD M3): fit on episodes [0, i), test on i.

Only out-of-sample (test) values are reported as policy numbers; the in-sample
training score is kept alongside so the train/test gap is visible.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

import numpy as np
from numpy.typing import NDArray

from asaudit.eval.optimize import OptimizeResult

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Fold:
    test_index: int
    train_indices: tuple[int, ...]
    train_value: float
    test_value: float
    params: NDArray[np.float64]
    converged: bool
    evaluations: int


def walk_forward(
    episodes: Sequence[T],
    min_train: int,
    fit: Callable[[Sequence[T], NDArray[np.float64] | None], OptimizeResult],
    evaluate: Callable[[T, NDArray[np.float64]], float],
) -> list[Fold]:
    if min_train < 1 or min_train >= len(episodes):
        raise ValueError("need at least one training and one test episode")
    folds: list[Fold] = []
    warm: NDArray[np.float64] | None = None
    for i in range(min_train, len(episodes)):
        result = fit(episodes[:i], warm)
        warm = result.x
        folds.append(
            Fold(
                i,
                tuple(range(i)),
                result.value,
                evaluate(episodes[i], result.x),
                result.x,
                result.converged,
                result.evaluations,
            )
        )
    return folds
