"""A3 off: observed depth dynamics, unmodified by our presence."""

from asaudit.types import IntensityAdjustment, LevelContext


class FrozenBook:
    name = "frozen"

    def adjust_intensities(
        self, level_depth_with_us: int, level_depth_observed: int, ctx: LevelContext | None
    ) -> IntensityAdjustment:
        return IntensityAdjustment(1.0, 1.0)
