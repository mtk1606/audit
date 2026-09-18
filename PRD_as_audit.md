# PRD: `as-audit`

**An empirical audit and correction of the Avellaneda-Stoikov market-making model**

Version 1.0 · Spec for autonomous implementation by Claude Code

---

## 0. How to use this document

You are implementing a research codebase, not a product. The output that matters is a set of **falsifiable measurements** plus the infrastructure that makes them reproducible by a third party.

Rules of engagement:

1. **Work milestone by milestone.** M0 → M5. Do not begin a milestone until the previous milestone's acceptance criteria pass and its artifacts are committed.
2. **Do not skip M1.** Every downstream claim is discountable without a correct faithful replication.
3. **Never silently substitute an approximation.** If a spec item is infeasible, stop, write the blocker into `docs/DECISIONS.md` with the options and your recommendation, and surface it rather than shipping a quiet workaround.
4. **Every number that appears in a report must be reproducible from a committed config plus a data checksum.** No hand-edited numbers, no numbers pasted from a notebook.
5. Items marked `TODO(verify)` must be checked against the primary source before use. Do not trust values reproduced here from memory.

---

## 1. Problem statement

Avellaneda & Stoikov (2008), *High-frequency trading in a limit order book*, Quantitative Finance 8(3), 217-224, gives the canonical closed form for inventory-aware optimal quoting. It models fill arrival as a Poisson process with intensity `λ(δ) = A·exp(−k·δ)`, where `δ` is quote distance from the mid.

That single assumption encodes three things that are false in every real electronic market:

| ID | Assumption | Reality |
|---|---|---|
| **A1** | Fill probability depends on distance from mid | Fill probability depends overwhelmingly on **queue position** at a price level. Two makers at the same price have different fill rates. |
| **A2** | Fills are informationally neutral | Fills arrive disproportionately when the price is about to move against you. Adverse selection is the dominant cost of market making and AS has no term for it. |
| **A3** | You quote alone, with no reaction | Other participants observe depth and adjust join/cancel behaviour; your own quote changes the flow you receive. |

Practitioners know all three. What does not exist publicly is a **decomposition of how much each assumption costs**, or a principled correction derived from that decomposition.

### 1.1 Thesis under test

> The Avellaneda-Stoikov reservation price is systematically biased in the presence of queue position and adverse selection, the bias is measurable and decomposable by assumption, and a corrected quoting rule recovers a quantifiable fraction of the shortfall against a policy-class optimum.

### 1.2 Pre-registration requirement

Before any M3 result is computed, commit `PREREGISTRATION.md` containing: the thesis above, the primary metric, the regime definitions, the statistical tests, the significance threshold, and an explicit statement that the negative result (corrections are small, AS is adequate) will be published with equal prominence. Commit it, tag it, do not edit it afterward. Amendments go in a dated appendix.

---

## 2. Scope

### In scope

- Faithful replication of AS 2008 simulation results
- A limit-order-book replay simulator with independently switchable fill, information, and competition mechanics
- Calibration of each mechanism from real L3 data
- Exact Shapley attribution of the P&L gap across A1/A2/A3
- Regime-conditional reporting (spread, volatility, queue depth)
- A corrected quoting rule with queue and adverse-selection terms
- A packaged, versioned open benchmark

### Out of scope (non-goals)

- Live or paper trading, order routing, exchange connectivity
- Latency modelling beyond a single configurable constant delay
- Multi-venue, cross-asset, or options market making
- Alpha signals beyond those needed to define regimes
- Anything requiring paid data as a hard dependency (paid data may be an optional adapter)
- Scale beyond a single machine

---

## 3. Success criteria

| Level | Criterion |
|---|---|
| **Floor** | M1 passes: AS 2008 numerical results reproduced within Monte Carlo error, from a re-derivation, with tests. |
| **Target** | M3 delivers a per-assumption attribution in basis points with bootstrap confidence intervals, stable across at least 5 tickers and 20 sessions, reported by regime. |
| **Stretch** | M4 delivers a corrected quoting rule that closes a statistically significant fraction of the gap on held-out data, with the shortfall closure reported as a point estimate and CI. |
| **Publication** | M5 ships a benchmark package a third party can `pip install`, point at LOBSTER sample data, and reproduce every figure with one command. |

The project is a success at **Target** even if the corrections turn out small. Design the reporting so a null result is presentable, not embarrassing.

---

## 4. Three design decisions that override the naive reading of the brief

These are load-bearing. Implement them as written.

### 4.1 The baseline is a *policy-class optimum*, not "the empirical optimum"

An unrestricted "empirically optimal quoting policy" is not identifiable from historical data and invites overfitting that will be spotted immediately by any competent reader. Instead:

Define an explicit **policy class** and optimise within it under walk-forward validation.

```python
# Linear skew policy class
δ_bid = clip(a0 + a1*q + a2*σ̂ + a3*imb + a4*depth_ratio, δ_min, δ_max)
δ_ask = clip(b0 + b1*q + b2*σ̂ + b3*imb + b4*depth_ratio, δ_min, δ_max)
```

Name it `PolicyClassOptimum` everywhere in code, figures, and prose. Report the train/test gap for every fitted policy. The claim is "AS leaves N bps on the table relative to the best linear-skew policy fitted out of sample," which is defensible, not "relative to the optimal policy," which is not.

Support at least two policy classes so the result is not an artifact of one: `linear_skew` and `tabular_binned` (piecewise-constant over discretised state).

### 4.2 A3 (competition) is a calibrated response function, not an agent simulation

An agent-based sim of reactive quoters measures a property of your simulator, not of the market. Replace it with an **estimated elasticity**:

From L3 data, estimate join and cancel intensity at a price level as a function of observed level depth, book imbalance, and spread:

```
λ_join(level)   = f(depth, imbalance, spread, σ̂)
λ_cancel(level) = g(depth, imbalance, spread, σ̂, queue_age)
```

Then, when your order adds `v` units of depth to a level, apply the fitted response function to obtain the counterfactual join/cancel rates at the new depth. A3-on means the fitted elasticity is applied; A3-off means depth response is frozen at the observed value.

This makes A3 measurable and falsifiable. It is still the weakest of the three axes: document that explicitly in the writeup, report it with the widest error bars, and state the identification assumption (that the depth response estimated across the observed depth distribution extrapolates to the counterfactual depth your order creates).

Keep the agent-based reactive model as an **optional sensitivity analysis** in `sim/competition/reactive_agents.py`, clearly labelled as illustrative, never as a headline number.

### 4.3 Counterfactual fills are reported as bounds, not point estimates

You cannot observe whether your order would have filled. The ambiguity is concentrated in one unobservable: which cancellations at your price level occurred ahead of you versus behind you.

Implement three cancellation-attribution policies and run all three:

| Policy | Assumption | Role |
|---|---|---|
| `pessimistic` | All cancels occur behind you | Lower fill bound |
| `uniform` | Cancels distributed proportionally across the queue | **Headline** |
| `optimistic` | All cancels occur ahead of you | Upper fill bound |

Every headline number ships with its bound interval. If the qualitative conclusion flips between `pessimistic` and `optimistic`, say so prominently and do not report a headline.

---

## 5. Architecture

### 5.1 Stack

- Python 3.11+, `uv` for env and locking
- `numpy`, `polars` (not pandas), `numba` for the replay inner loop, `scipy`
- `pydantic` v2 for config schemas, `pydantic-settings` for env
- `pyarrow` / Parquet for all intermediate data, `duckdb` for ad-hoc queries
- `structlog` for JSON logging
- `pytest`, `hypothesis`, `pytest-benchmark`
- `matplotlib` only (no seaborn, no plotly) so figures are deterministic and dependency-light
- `typer` for CLI
- `ruff`, `mypy --strict` on `src/`

Do not reach for Rust or C++ unless `pytest-benchmark` shows the numba replay loop missing the performance budget in §10. The event loop is isolated behind `SimEngine` so a native core can be swapped in later without touching callers.

### 5.2 Repository layout

```
as-audit/
├── pyproject.toml
├── README.md
├── PREREGISTRATION.md
├── docs/
│   ├── DECISIONS.md            # ADR log, append-only
│   ├── DERIVATION.md           # AS re-derivation + M4 correction derivation
│   └── DATA.md                 # provenance, licences, checksums
├── configs/
│   ├── replication/as2008.yaml
│   ├── calibration/{intensity,queue,adverse,elasticity}.yaml
│   ├── ablation/full_grid.yaml
│   └── policy/{linear_skew,tabular_binned}.yaml
├── src/asaudit/
│   ├── types.py                # frozen dataclasses, no logic
│   ├── config.py               # pydantic models, one per config file
│   ├── logging.py              # structlog setup, run manifest
│   ├── strategy/
│   │   ├── base.py             # Quoter protocol
│   │   ├── symmetric.py        # AS naive benchmark
│   │   ├── avellaneda_stoikov.py
│   │   ├── policy_class.py     # linear_skew, tabular_binned
│   │   └── corrected.py        # M4
│   ├── sim/
│   │   ├── engine.py           # event loop
│   │   ├── book.py             # L3 book reconstruction + own-order tracking
│   │   ├── accounting.py       # P&L, markout, inventory
│   │   ├── fills/{base,poisson,queue}.py
│   │   ├── flow/{base,neutral,calibrated_markout}.py
│   │   └── competition/{base,frozen,elasticity,reactive_agents}.py
│   ├── data/
│   │   ├── schema.py           # canonical event schema
│   │   ├── lobster.py          # LOBSTER adapter
│   │   ├── crypto_l3.py        # Coinbase full-channel adapter + collector
│   │   ├── quality.py          # DataQualityReport
│   │   └── regimes.py          # regime tagging
│   ├── calibration/
│   │   ├── intensity.py        # A, k
│   │   ├── queue_fill.py       # P(fill | queue pos, depth, ...)
│   │   ├── adverse.py          # markout curves
│   │   └── elasticity.py       # join/cancel response
│   ├── attribution/
│   │   ├── grid.py             # 2^3 ablation runner
│   │   ├── shapley.py          # exact Shapley over 3 axes
│   │   └── metrics.py
│   ├── eval/
│   │   ├── backtest.py
│   │   ├── bootstrap.py        # stationary block bootstrap
│   │   └── walkforward.py
│   └── report/
│       ├── figures.py
│       └── tables.py
├── scripts/
│   ├── collect_crypto_l3.py    # long-running, restartable
│   └── fetch_lobster_sample.py
├── tests/
│   ├── unit/
│   ├── property/
│   ├── golden/
│   └── integration/
└── results/                    # gitignored; manifests committed
```

### 5.3 Core interfaces

Define these first, in `types.py` and the `base.py` modules, before any implementation. All dataclasses `frozen=True, slots=True`. Timestamps are `int` nanoseconds since epoch, never floats.

```python
# types.py

class Side(IntEnum):
    BID = 1
    ASK = -1

@dataclass(frozen=True, slots=True)
class LOBEvent:
    ts_ns: int
    event_type: EventType      # ADD, CANCEL, DELETE, EXECUTE, EXECUTE_HIDDEN, HALT
    order_id: int
    side: Side
    price_ticks: int           # integer ticks, never float prices
    size: int

@dataclass(frozen=True, slots=True)
class BookSnapshot:
    ts_ns: int
    bid_px_ticks: np.ndarray   # shape (K,), descending
    bid_sz: np.ndarray
    ask_px_ticks: np.ndarray   # shape (K,), ascending
    ask_sz: np.ndarray

    @property
    def mid(self) -> float: ...
    @property
    def microprice(self) -> float: ...
    @property
    def spread_ticks(self) -> int: ...

@dataclass(frozen=True, slots=True)
class MarketState:
    ts_ns: int
    book: BookSnapshot
    sigma_hat: float           # rolling realized vol, per-second units
    imbalance: float           # (bid_sz0 - ask_sz0) / (bid_sz0 + ask_sz0)
    time_remaining: float      # normalized (T - t) in [0, 1]
    inventory: int
    cash: float
    regime: RegimeTag

@dataclass(frozen=True, slots=True)
class Quote:
    ts_ns: int
    bid_px_ticks: int | None
    bid_size: int
    ask_px_ticks: int | None
    ask_size: int

@dataclass(frozen=True, slots=True)
class Fill:
    ts_ns: int
    side: Side                 # side of OUR resting order
    price_ticks: int
    size: int
    queue_pos_at_entry: int
    queue_pos_at_fill: int
    mid_at_fill: float
    is_bounded_estimate: bool  # True if produced under a cancel-attribution policy

@dataclass(frozen=True, slots=True)
class OwnOrderState:
    order_id: int
    side: Side
    price_ticks: int
    size_remaining: int
    queue_ahead: int           # units of volume ahead of us at this level
    entry_ts_ns: int
```

```python
# strategy/base.py

class Quoter(Protocol):
    name: str

    def reset(self, ctx: EpisodeContext) -> None:
        """Called once per episode. Must clear all internal state."""

    def on_market_update(self, s: MarketState) -> Quote | None:
        """Return the desired quote, or None to leave existing quotes resting."""

    def on_fill(self, f: Fill, s: MarketState) -> None:
        """Notification only. Inventory accounting is the engine's job, not the quoter's."""
```

```python
# sim/fills/base.py

class FillModel(Protocol):
    name: str

    def step(
        self,
        own_orders: Mapping[int, OwnOrderState],
        events: Sequence[LOBEvent],     # events in [t, t+Δt)
        book_before: BookSnapshot,
        rng: np.random.Generator,
    ) -> tuple[list[Fill], Mapping[int, OwnOrderState]]:
        """Advance own orders through one batch of market events.
        Returns fills produced and the updated own-order state."""
```

```python
# sim/flow/base.py

class InformationModel(Protocol):
    """Determines the price path conditional on our fills."""
    name: str

    def mid_after(self, f: Fill, horizon_ns: int, observed_mid: float,
                  rng: np.random.Generator) -> float: ...
```

```python
# sim/competition/base.py

class CompetitionModel(Protocol):
    name: str

    def adjust_intensities(
        self, level_depth_with_us: int, level_depth_observed: int,
        ctx: LevelContext,
    ) -> IntensityAdjustment:
        """Return multiplicative adjustments to join and cancel intensity at a level
        given that our order changed its depth."""
```

### 5.4 The ablation grid

Three binary axes, eight configurations. Axis "off" = the AS assumption; axis "on" = the empirically calibrated mechanism.

| Axis | Off (AS) | On (empirical) |
|---|---|---|
| A1 | `PoissonFillModel` | `QueueFillModel` |
| A2 | `NeutralFlow` | `CalibratedMarkoutFlow` |
| A3 | `FrozenBook` | `ElasticityCompetition` |

`(off, off, off)` must reproduce M1 exactly. Assert this in an integration test: it is the seam where a bug will hide.

---

## 6. Milestones

### M0 — Scaffold and data spine

**Build**

- Repo skeleton, `pyproject.toml`, CI (ruff + mypy strict + pytest on push)
- `types.py` and all `base.py` protocols, fully typed, zero implementation
- LOBSTER adapter producing canonical `LOBEvent` streams from the free sample (AMZN, AAPL, GOOG, INTC, MSFT, 2012-06-21, levels 1-10) `TODO(verify)` the sample contents
- Crypto L3 collector: `scripts/collect_crypto_l3.py`, Coinbase full channel, restartable, sequence-gap detection, Parquet output partitioned by `symbol/date/hour`
- `DataQualityReport`: per-session counts of sequence gaps, crossed books, zero-size levels, halts, clock reversals. Fail the session load if gaps exceed a configured threshold. Never forward-fill silently.

**Acceptance**

- `asaudit data validate --source lobster --symbol AAPL --date 2012-06-21` prints a quality report and exits 0
- Book reconstruction from the event stream matches the LOBSTER-provided orderbook file at every message index, exactly, for all 5 tickers
- The crypto collector runs for 1 hour unattended, survives a forced disconnect, and produces a gap-free session

**Start the crypto collector on day one.** The dataset compounds while everything else is built.

---

### M1 — Faithful AS replication

**Build**

- `docs/DERIVATION.md`: derive the AS solution from the HJB, showing the exponential-utility transformation and the frozen-inventory approximation. Do not copy a public implementation. A large fraction of open AS implementations carry sign errors in the inventory term, and this derivation is what makes the rest of the project credible.
- `strategy/avellaneda_stoikov.py`:

```
reservation price:   r(s, q, t) = s − q·γ·σ²·(T − t)
optimal total spread: δ_a + δ_b = γ·σ²·(T − t) + (2/γ)·ln(1 + γ/k)
quotes:              p_b = r − (δ_a + δ_b)/2,   p_a = r + (δ_a + δ_b)/2
fill intensity:      λ(δ) = A·exp(−k·δ)
```

- `strategy/symmetric.py`: the naive inventory-independent benchmark from the paper
- Monte Carlo harness reproducing the paper's numerical experiment

**Paper parameters** `TODO(verify all against the paper before running`):
`s0 = 100, T = 1, σ = 2, dt = 0.005, q0 = 0, γ = 0.1, k = 1.5, A = 140, n_paths = 1000`, arithmetic Brownian mid.

**Expected targets** `TODO(verify)` — extract the exact table from the paper and encode it in `tests/golden/as2008_table.json`:
inventory strategy ≈ profit 65.0, std 6.6, final inventory ≈ 0, std ≈ 2.9; symmetric strategy ≈ profit 68.4, std 13.4, final inventory std ≈ 8.4. The headline is the roughly 2x variance reduction at slightly lower mean profit.

**Acceptance**

- Reproduced means and standard deviations fall within the Monte Carlo 95% CI of the paper's reported values at `n_paths = 1000`, tested in `tests/golden/test_as_replication.py`
- Variance-reduction ratio reproduced within 10% relative
- Unit tests: reservation price equals mid at `q = 0`; equals mid at `t = T`; is monotone decreasing in `q`; spread is monotone increasing in `σ` and in `(T − t)`; spread limit as `γ → 0` matches `2/k · ln(...)` expansion
- `docs/DERIVATION.md` reviewed and committed

**Ship this.** M1 alone is a standalone artifact: a verified open replication of AS 2008. Publish it before starting M2.

---

### M2 — The ablation testbed

**Build**

`sim/engine.py`. Event-driven loop over the replayed L3 stream:

```
for each event batch in [t, t + Δt):
    1. advance market book with events
    2. apply competition model to obtain adjusted join/cancel intensities
    3. advance own orders through the fill model → fills
    4. apply information model → realized mid path for markout accounting
    5. update accounting (cash, inventory, markouts)
    6. build MarketState
    7. call quoter.on_market_update → new Quote
    8. apply order latency (constant, configurable: 0 / 100µs / 1ms) before quote takes effect
    9. cancel/replace: any repriced order goes to the BACK of the new level queue
```

Step 9 is where naive simulators lie. Repricing must cost queue position.

**Fill models**

`PoissonFillModel`: draw fills from `λ(δ) = A·exp(−k·δ)` with `(A, k)` from `calibration/intensity.py` fitted to the session, so it is comparable to the queue model on the same data rather than to paper constants.

`QueueFillModel`: track `queue_ahead` per own order. Decrement on executions at that level. Decrement on cancellations ahead of us per the active cancel-attribution policy (§4.3). Fill when cumulative execution volume at the level exceeds `queue_ahead`. Handle partial fills, hidden-order executions, and level deletion.

**Information models**

`NeutralFlow`: the observed mid path, independent of our fills.

`CalibratedMarkoutFlow`: our fills are drawn to match the empirical markout distribution conditional on `(queue position, spread regime, imbalance)` estimated in `calibration/adverse.py`. Under `QueueFillModel` on real data the markout is directly observed, so this model exists to make A2 switchable while A1 is off, which is what makes the 2×2×2 grid coherent.

**Competition models**

`FrozenBook`: observed depth dynamics, unmodified.
`ElasticityCompetition`: apply the fitted join/cancel response (§4.2).
`ReactiveAgents` (optional, labelled illustrative).

**Calibration modules**

- `intensity.py`: fit `A, k` by regressing log fill count on distance-from-mid buckets; report `R²` and residual structure, because the visible misfit of the exponential form is itself a finding worth a figure
- `queue_fill.py`: estimate `P(fill within horizon | queue_ahead, level depth, spread, σ̂, imbalance)`; start with a logistic model, escalate to gradient boosting only if the logistic residuals are structured, and if you escalate keep the logistic as the headline for interpretability
- `adverse.py`: markout curves `E[side · (mid_{t+h} − fill_px)]` at `h ∈ {100ms, 1s, 10s, 60s}`, conditional on queue position and regime
- `elasticity.py`: join/cancel intensity as a function of level depth, imbalance, spread, σ̂

**Acceptance**

- `(A1=off, A2=off, A3=off)` reproduces M1 within Monte Carlo error, asserted in `tests/integration/test_grid_reduces_to_as.py`
- Property tests (hypothesis) pass: cash + inventory·mid equals cumulative P&L at every step; no fill ever occurs at a price through the opposite side; `queue_ahead` is non-increasing except on own reprice; inventory equals the signed sum of fills; a reprice strictly increases `queue_ahead` when the target level has existing depth
- Golden-file regression: fixed seed and fixed config produce byte-identical fill sequences across runs and across machines
- Each of the 8 grid configs runs to completion on one LOBSTER session
- Bounds sanity: `pessimistic` fill count ≤ `uniform` ≤ `optimistic` for every session

---

### M3 — Attribution

**Build**

- `attribution/grid.py`: run all 8 configs × {strategies} × {sessions} × {cancel policies}. Strategies: `AvellanedaStoikov`, `Symmetric`, `PolicyClassOptimum(linear_skew)`, `PolicyClassOptimum(tabular_binned)`.
- `eval/walkforward.py`: policy-class optimisation uses expanding-window walk-forward. Fit on sessions `[0, i)`, evaluate on session `i`. Never report an in-sample policy number.
- `attribution/shapley.py`: exact Shapley over 3 binary axes. Eight coalitions is the complete grid, so compute the exact value, not a sample. Each axis's attribution is its mean marginal contribution across the 3! = 6 orderings.
- `eval/bootstrap.py`: stationary block bootstrap over sessions for CIs on every headline number. Block length selected by the Politis-White automatic rule.
- `data/regimes.py`: terciles of time-weighted spread, of realized 1-minute vol, and of top-of-book depth, computed per symbol over the full sample. Report axis marginals plus the spread × volatility interaction. Do not report the full 3×3×3 cell grid; the cells are too sparse to be meaningful.

**Primary metric**

`gap_bps = (PnL_policy_class_optimum − PnL_strategy) / notional_traded × 10_000`

Report per strategy, per regime, per cancel-attribution policy, with bootstrap CIs.

**Acceptance**

- Shapley attributions sum to the total gap, to floating-point tolerance, asserted in a unit test
- Attribution signs and rank ordering are stable across ≥5 symbols and ≥20 sessions
- Every headline number has a bootstrap CI and a bound interval
- The A2 (adverse selection) attribution is computed and reported **first**, since prior belief says it is the largest and it is the number that decides whether this project is interesting

**Primary figure**

A single stacked bar: total AS shortfall in bps decomposed into A1, A2, A3, with error bars, repeated as a small-multiple panel across regimes. This figure has to be legible with no caption.

---

### M4 — The correction

Gate: do not start until M3 attributions are stable and signed off.

**Build**

- Extend `docs/DERIVATION.md`. Re-derive the HJB with two modifications:
  1. **Queue-conditional intensity.** Replace `λ(δ)` with `λ(δ, Q)` where `Q` is expected queue position at the quoted level. Use the functional form fitted in `calibration/queue_fill.py`.
  2. **Informed flow.** Introduce `β_b = E[Δ mid | fill on our bid]` and `β_a` symmetrically. The effective fill price becomes the quoted price plus the expected adverse move, which skews the optimal quote asymmetrically.
- Solve in closed form if the modified HJB admits one. If not, produce a semi-analytic approximation (asymptotic expansion in small `γ`, or numerical solution on a state grid with a fitted closed-form surrogate). Document which you got and why.
- `strategy/corrected.py`: implement the result. Expected shape, to be confirmed by the derivation, not assumed:

```
r_corrected = s − q·γ·σ²·(T − t) − (β_a − β_b)/2          # adverse-selection skew
δ_corrected = δ_AS + f(Q; k_eff) + (β_a + β_b)/2           # queue + AS widening
```

- Evaluate on **held-out sessions not used for any calibration or policy fitting**. Maintain a strict three-way split: calibration / policy-fitting / held-out. The held-out set is touched once.

**Acceptance**

- Corrected rule beats AS on held-out data with a bootstrap CI excluding zero, or the negative result is reported with equal prominence
- Shortfall closure reported as a fraction of the M3 gap, with CI
- Ablation of the correction's own two terms (queue term only, adverse term only, both) so the reader sees which term carries the result
- Sensitivity sweep over quote size ∈ {1, 10, 100} lots, since the zero-own-impact assumption degrades with size

---

### M5 — Release

**Build**

- `pip install as-audit`; `asaudit reproduce --paper` regenerates every figure and table from the LOBSTER sample in one command on a clean machine
- Pinned lockfile, Dockerfile, and a CI job that runs the full reproduction on the sample data
- `benchmarks/`: the packaged AS benchmark. A `Quoter` implementation plus a config is all a third party should need to submit a strategy and get a comparable number.
- Writeup: title it on the finding, *"Avellaneda-Stoikov assumes you're alone at the front of the queue."* Lead with the stacked-bar figure. Structure: finding, replication, method, attribution, correction, limitations, reproduction instructions.
- A limitations section that names, without hedging: the identification assumption behind A3, the cancel-attribution ambiguity, the zero-own-impact assumption, the policy-class-not-global-optimum framing, and the sample period.

**Acceptance**

- A clean container, given only the repo and the public LOBSTER sample, reproduces every reported number
- `README.md` states the headline result in the first three lines

---

## 7. Configuration and reproducibility

Every run is defined by a config file. No CLI flag may change a scientific parameter; flags control paths, parallelism, and verbosity only.

```yaml
# configs/ablation/full_grid.yaml
run_name: ablation_v1
seed: 20260913

data:
  source: lobster
  symbols: [AAPL, AMZN, GOOG, INTC, MSFT]
  sessions: {start: 2012-06-21, end: 2012-06-21}
  splits: {calibration: 0.4, policy_fit: 0.3, holdout: 0.3}
  quality: {max_gap_pct: 0.001, fail_on_crossed_book: true}

sim:
  tick_size: 0.01
  quote_size: 10
  latency_ns: 100_000
  episode_length_s: 300
  max_inventory: 200

grid:
  fill: [poisson, queue]
  flow: [neutral, calibrated_markout]
  competition: [frozen, elasticity]
  cancel_attribution: [pessimistic, uniform, optimistic]

strategies:
  - {name: avellaneda_stoikov, gamma: 0.1, calibrate_Ak: true}
  - {name: symmetric, spread_ticks: 2}
  - {name: policy_class, klass: linear_skew, optimizer: cma_es, budget: 2000}
  - {name: policy_class, klass: tabular_binned, bins: {q: 9, sigma: 3, imb: 5}}

eval:
  markout_horizons_ns: [100_000_000, 1_000_000_000, 10_000_000_000, 60_000_000_000]
  bootstrap: {method: stationary_block, n: 10_000}
```

**Run manifest.** Every run writes `results/<utc_ts>_<git_sha>_<config_hash>/manifest.json`:

```json
{
  "run_id": "...", "git_sha": "...", "git_dirty": false,
  "config_hash": "sha256:...", "config": {...},
  "data_checksums": {"lobster/AAPL/2012-06-21": "sha256:..."},
  "env": {"python": "3.11.9", "numpy": "2.1.0", "platform": "..."},
  "seed": 20260913,
  "started_utc": "...", "finished_utc": "...",
  "n_events": 412_339, "n_fills": 1_842,
  "data_quality": {"gaps": 0, "crossed_books": 3, "halts": 0}
}
```

Refuse to run with a dirty git tree unless `--allow-dirty` is passed, and record that flag in the manifest.

---

## 8. Error handling and logging

**Fail fast, loudly, on data.** Sequence gaps, crossed books, negative sizes, non-monotonic timestamps, and unknown event types raise `DataQualityError` with the offending event index and the surrounding 10 events. Do not repair data implicitly. Repairs, if any, are explicit config options that appear in the manifest.

**Never swallow an exception in the event loop.** A failed session aborts that session, records the failure in the run manifest with a traceback, and continues to the next session. A run whose failed-session fraction exceeds 5% exits non-zero.

**Structured logging.** `structlog` JSON to file, human-readable to console. Every log line carries `run_id`, `session_id`, `config_hash`. Log levels:

- `ERROR`: session aborted, calibration failed to converge, acceptance assertion failed
- `WARN`: fit `R²` below threshold, bootstrap CI wider than the point estimate, cancel-attribution bounds straddling zero, inventory hitting its cap more than 1% of the time
- `INFO`: milestone-level progress, one line per session with fill count and P&L
- `DEBUG`: per-event tracing, off by default, gated behind a config flag because it dominates runtime

**Numerical guards.** Assert finite P&L and finite quote prices every step. `RuntimeWarning` is promoted to an error under `numpy.errstate`. The optimiser reports convergence status and the number of restarts; a non-converged fit is a hard failure, not a logged warning.

**Determinism.** One seeded `np.random.Generator` per (session, config), derived from the run seed via `SeedSequence.spawn`. No global RNG state. Verified by the golden-file test.

---

## 9. Testing

| Layer | Content | Gate |
|---|---|---|
| **Unit** | Closed-form AS identities, markout arithmetic, tick/price conversions, regime tagging boundaries, Shapley sums to total | Every commit |
| **Property** (hypothesis) | Accounting identity, no through-the-book fills, queue monotonicity, reprice costs queue, fill bounds ordering | Every commit |
| **Golden** | AS 2008 replication table; fixed-seed fill sequences; one full ablation run on a 5-minute fixture | Every commit |
| **Integration** | Book reconstruction vs LOBSTER orderbook file; `(off,off,off)` reduces to M1; end-to-end `asaudit reproduce --paper` | Nightly + release |
| **Benchmark** | Replay throughput vs budget in §10 | Nightly, fails on >20% regression |

Coverage target 85% on `src/asaudit/{sim,strategy,calibration,attribution}`. Coverage on `report/` is not a goal.

Fixtures: commit a 5-minute LOBSTER slice (check the licence in `docs/DATA.md` before committing any raw data; if redistribution is not permitted, commit a synthetic event stream with the same statistical structure and a fetch script for the real slice).

---

## 10. Performance budget

| Operation | Budget |
|---|---|
| Replay one LOBSTER session (~400k messages, level-10) for one config | ≤ 30 s single core |
| Full ablation grid (8 configs × 3 cancel policies × 4 strategies × 5 symbols × 1 session) | ≤ 30 min on 8 cores |
| Policy-class optimisation, one class, one walk-forward fold | ≤ 10 min |
| Peak RSS | ≤ 8 GB |

Profile before optimising. Expected hot path is `QueueFillModel.step` and book mutation: numba-jit those two, leave everything else in plain Python. If the budget is missed by more than 3x after jitting, stop and write up the options in `docs/DECISIONS.md` rather than starting a rewrite.

---

## 11. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Corrections turn out small, AS is adequate | Medium | Pre-registered as a publishable negative result. Measure A2 first, since it is the term most likely to be large and it determines whether to continue. |
| Cancel-attribution bounds are so wide the result is uninformative | Medium | Report bounds honestly; use L3 order IDs to narrow attribution where the data permits; if bounds straddle zero, that is itself the finding about counterfactual backtesting. |
| Policy-class optimum overfits and the gap is illusory | Medium | Walk-forward only, two policy classes, train/test gap reported alongside every number. |
| A3 elasticity does not extrapolate to counterfactual depth | High | Widest error bars, explicit identification assumption, reported as the weakest axis. |
| LOBSTER sample is a single day and results do not generalise | High | Crypto L3 collection from day one gives a long, independent, full-depth sample. Report both, and treat agreement across the two as the generalisation evidence. |
| Scope creep into M4 before M3 is stable | High | Hard gate. M4 does not start until M3 acceptance criteria pass. |
| Simulator bug that inflates the finding | Medium | `(off,off,off)` must reduce to M1; property tests on accounting; golden files; publish the simulator. |

---

## 12. Deliverables checklist

- [ ] `as-audit` repo, MIT or Apache-2.0, CI green
- [ ] `PREREGISTRATION.md`, committed and tagged before M3 results
- [ ] `docs/DERIVATION.md` with the AS re-derivation and the M4 correction derivation
- [ ] M1 standalone artifact: verified open replication of AS 2008
- [ ] Ablation testbed with three independently switchable assumptions
- [ ] Attribution table: bps per assumption, per regime, with CIs and bounds
- [ ] The stacked-bar decomposition figure, legible without a caption
- [ ] Corrected quoting rule, evaluated once on held-out data
- [ ] Packaged benchmark with one-command reproduction
- [ ] Writeup with an unhedged limitations section
