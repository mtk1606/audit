import numpy as np
import pytest
from fixtures import calibration, session

from asaudit.calibration.adverse import MarkoutTable, executions
from asaudit.calibration.elasticity import fit_elasticity
from asaudit.calibration.glm import CalibrationError, fit_glm
from asaudit.calibration.intensity import fit_intensity
from asaudit.types import EventType


def test_synthetic_book_is_never_crossed_or_empty():
    s = session(1, 300.0)
    assert (s.bid_sz[:, 0] > 0).all() and (s.ask_sz[:, 0] > 0).all()
    assert (s.ask_px[:, 0] > s.bid_px[:, 0]).all()
    assert (np.diff(s.ts_ns) >= 0).all()
    assert set(np.unique(s.event_type)) <= {
        int(EventType.ADD),
        int(EventType.DELETE),
        int(EventType.EXECUTE),
    }


def test_book_rows_match_event_deltas_at_touch():
    # Touch depth moves by exactly the event size when an event hits an unchanged touch.
    s = session(2, 120.0)
    checked = 0
    for i in range(s.n_events):
        side = int(s.side[i])
        px, sz = (s.bid_px, s.bid_sz) if side == 1 else (s.ask_px, s.ask_sz)
        if px[i, 0] == s.price[i] and px[i + 1, 0] == s.price[i]:
            sign = 1 if s.event_type[i] == int(EventType.ADD) else -1
            assert sz[i + 1, 0] - sz[i, 0] == sign * s.size[i]
            checked += 1
    assert checked > 100


def test_intensity_decreases_and_reports_fit_quality():
    fit = fit_intensity(session(3, 600.0))
    assert fit.k > 0 and fit.A > 0
    assert 0 <= fit.r2 <= 1 and len(fit.residuals) == len(fit.rates)
    assert (np.diff(fit.rates) <= 0).all()


@pytest.mark.parametrize("truth", [(-0.1, 0.8), (-0.8, 1.8)])
def test_join_elasticity_recovered(truth):
    fit = fit_elasticity(session(4, 900.0, join_elasticity=truth[0], cancel_elasticity=truth[1]))
    assert abs(fit.join_elasticity - truth[0]) < 0.2


def test_cancel_elasticity_comparative_statics():
    low = fit_elasticity(session(4, 900.0, join_elasticity=-0.1, cancel_elasticity=0.8))
    high = fit_elasticity(session(4, 900.0, join_elasticity=-0.8, cancel_elasticity=1.8))
    assert high.cancel_elasticity - low.cancel_elasticity > 0.5


def test_informed_flow_raises_measured_adverse_selection():
    informed = MarkoutTable(executions(session(5, 900.0), 1_000_000_000)).overall
    neutral = MarkoutTable(
        executions(session(5, 900.0, informed_weight=0.0), 1_000_000_000)
    ).overall
    assert informed > neutral > 0  # mechanical impact remains without information


def test_queue_fill_probability_falls_with_queue():
    fit = calibration().queue_fill
    assert fit.fit.coef[1] < 0
    assert fit.probability(1, 10, 0, 0) > fit.probability(40, 10, 0, 0)


def test_glm_rejects_underdetermined_and_nonconvergence():
    with pytest.raises(CalibrationError):
        fit_glm(np.ones((2, 3)), np.ones(2), "poisson")
    X = np.column_stack([np.ones(50), np.r_[np.zeros(25), np.ones(25)]])
    y = np.r_[np.zeros(25), np.ones(25)]  # perfectly separated: MLE does not exist
    with pytest.raises(CalibrationError):
        fit_glm(X, y, "logistic", ridge=0.0, max_iter=25)
