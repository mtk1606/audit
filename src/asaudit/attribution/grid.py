"""The 2^3 ablation grid: axis off = the AS assumption, on = calibrated mechanism."""

import itertools
from dataclasses import dataclass

from asaudit.calibration.bundle import Calibration
from asaudit.sim.competition.base import CompetitionModel
from asaudit.sim.competition.elasticity import ElasticityCompetition
from asaudit.sim.competition.frozen import FrozenBook
from asaudit.sim.fills.base import FillModel
from asaudit.sim.fills.poisson import PoissonFillModel
from asaudit.sim.fills.queue import CancelPolicy, QueueFillModel
from asaudit.sim.flow.base import InformationModel
from asaudit.sim.flow.calibrated_markout import CalibratedMarkoutFlow
from asaudit.sim.flow.neutral import NeutralFlow


@dataclass(frozen=True, slots=True)
class GridConfig:
    a1: bool  # queue fills
    a2: bool  # adverse selection
    a3: bool  # competition elasticity

    @property
    def label(self) -> str:
        return "".join("1" if x else "0" for x in (self.a1, self.a2, self.a3))


ALL_CONFIGS = tuple(GridConfig(*bits) for bits in itertools.product((False, True), repeat=3))


def build_models(
    g: GridConfig, cal: Calibration, policy: CancelPolicy
) -> tuple[FillModel, InformationModel, CompetitionModel]:
    fill: FillModel = (
        QueueFillModel(policy)
        if g.a1
        else PoissonFillModel(cal.intensity.A, cal.intensity.k, "saturate")
    )
    info: InformationModel
    if g.a2:
        info = CalibratedMarkoutFlow(cal.markout, embedded=fill.embeds_adverse_selection)
    else:
        info = NeutralFlow(cal.markout if fill.embeds_adverse_selection else None)
    competition: CompetitionModel = (
        ElasticityCompetition(cal.elasticity.join_elasticity, cal.elasticity.cancel_elasticity)
        if g.a3
        else FrozenBook()
    )
    return fill, info, competition
