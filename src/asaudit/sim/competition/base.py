from typing import Protocol

from asaudit.types import IntensityAdjustment, LevelContext


class CompetitionModel(Protocol):
    name: str

    def adjust_intensities(
        self, level_depth_with_us: int, level_depth_observed: int, ctx: LevelContext
    ) -> IntensityAdjustment: ...
