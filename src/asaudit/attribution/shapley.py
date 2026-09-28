"""Exact Shapley attribution over the three binary ablation axes (PRD M3).

v(S) is a metric under the configuration with exactly the axes in S switched
on. Each axis's value is its marginal contribution averaged over all 3! = 6
orderings, computed exactly from the eight grid cells. By efficiency the three
values sum to v(all) - v(none).
"""

import itertools
import math
from collections.abc import Mapping

AXES = ("A1", "A2", "A3")


def _label(on: frozenset[str]) -> str:
    return "".join("1" if axis in on else "0" for axis in AXES)


def shapley(values: Mapping[str, float]) -> dict[str, float]:
    """``values`` maps grid labels such as "010" to the metric; all 8 required."""
    expected = {"".join(bits) for bits in itertools.product("01", repeat=3)}
    if set(values) != expected:
        raise ValueError(f"need all 8 grid cells, got {sorted(values)}")
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("non-finite grid value")
    out = dict.fromkeys(AXES, 0.0)
    orders = list(itertools.permutations(AXES))
    for order in orders:
        on: frozenset[str] = frozenset()
        for axis in order:
            with_axis = on | {axis}
            out[axis] += values[_label(with_axis)] - values[_label(on)]
            on = with_axis
    return {axis: total / len(orders) for axis, total in out.items()}
