"""A3 on: fitted depth elasticity of other participants' join and cancel flow.

With total-level cancel intensity proportional to depth ** e_cancel, the
cancel flow of the OTHER orders at a level whose depth rises from D to D + v
scales by ((D + v) / D) ** (e_cancel - 1): total intensity at the new depth,
times the others' share D / (D + v). Joins scale by ((D + v) / D) ** e_join.

Identification assumption (PRD 4.2): the response estimated across the observed
depth distribution extrapolates to the counterfactual depth our order creates.
"""

import math

from asaudit.types import IntensityAdjustment, LevelContext


class ElasticityCompetition:
    name = "elasticity"

    def __init__(self, join_elasticity: float, cancel_elasticity: float) -> None:
        if not (math.isfinite(join_elasticity) and math.isfinite(cancel_elasticity)):
            raise ValueError("elasticities must be finite")
        self.join_elasticity = join_elasticity
        self.cancel_elasticity = cancel_elasticity

    def adjust_intensities(
        self, level_depth_with_us: int, level_depth_observed: int, ctx: LevelContext | None
    ) -> IntensityAdjustment:
        if level_depth_observed <= 0 or level_depth_with_us < level_depth_observed:
            return IntensityAdjustment(1.0, 1.0)
        ratio = level_depth_with_us / level_depth_observed
        return IntensityAdjustment(
            ratio**self.join_elasticity, ratio ** (self.cancel_elasticity - 1)
        )
