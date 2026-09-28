# as-audit

**Avellaneda-Stoikov assumes you're alone at the front of the queue. This repository measures what that assumption costs.**

The first milestone is complete, with a qualification. The published AS 2008 tables are reproduced as an exactly computed discrete law with capped fill probabilities. All 27 printed values are consistent with it (max |z| = 1.88). The two alternatives, Poisson fill probabilities and finer time steps, are rejected. The attribution machinery (queue position A1, adverse selection A2, competition A3) is built and verified on synthetic L3 data. It has **not yet been run on market data**, so there is no market headline yet.

## Status by milestone

| Milestone | State | Read |
|---|---|---|
| M0 data spine | User-accepted; live collector run outstanding | [M0](docs/reports/M0.md) |
| M1 AS 2008 replication | Complete, qualified, **pending owner adoption of the amended criterion** | [sensitivity study](docs/reports/M1-sensitivity.md), [original contract](docs/reports/M1-qf2008.md) |
| M2 ablation testbed | Built; every property test passes on synthetic L3; (off, off, off) reduces to the M1 law | [M2](docs/reports/M2.md) |
| M3 attribution | Pipeline built and exercised on a fixture; market run blocked on data access and pre-registration | [M3](docs/reports/M3.md) |
| M4 correction | Derived (semi-analytic), implemented, holdout gate built; not evaluated | [derivation draft](docs/DERIVATION_M4.draft.md) |
| M5 release | Reproduce command, benchmark, Dockerfile, nightly CI; not yet run remotely | [operations](docs/OPERATIONS.md) |

## Reproduce

```bash
uv sync --locked
uv run asaudit m1-sensitivity                          # M1, deterministic, ~5 min
uv run asaudit reproduce --paper --fixture --workers 4 # everything, synthetic L3
uv run python scripts/fetch_lobster_sample.py          # market data (network needed)
uv run asaudit reproduce --paper --workers 8           # everything, LOBSTER sample
```

Python 3.11+ and a clean Git checkout are required. Every run writes a manifest with the git SHA, config hash, input checksums, seeds and environment.

## How the M1 question was settled

The paper does not say what happens when `lambda * dt > 1`. Rather than compare the printed numbers with one seeded simulation (noise against noise), the population moments of each candidate law are computed exactly: a finite-state recurrence up to fourth order, checked against exhaustive path enumeration. Each printed value is then tested against the sampling distribution of the paper's own n = 1000 estimate. The protocol was committed before any number was computed. One by-product: the PRD's "variance ratio within 10%" criterion is tighter than the paper's own sampling error (about 8% SE on that ratio).

## How the attribution works

Three binary switches, eight cells. Off means the AS assumption; on means a mechanism calibrated from L3 data.

| Axis | Off | On |
|---|---|---|
| A1 queue | `PoissonFillModel` (the M1 law) | `QueueFillModel`: FIFO position, three cancel-attribution bounds |
| A2 information | `NeutralFlow` | `CalibratedMarkoutFlow`: conditional adverse move per fill |
| A3 competition | `FrozenBook` | `ElasticityCompetition`: fitted depth response of other liquidity |

The reference is a **PolicyClassOptimum** (linear-skew or tabular policy) fitted by expanding-window walk-forward, never in-sample. The shortfall is split into A1, A2 and A3 by exact Shapley values. Every number carries a stationary block bootstrap interval (Politis-White block length) and a pessimistic/optimistic cancel-attribution bound. A2 is always reported first.

## Guarantees enforced by tests

- The (off, off, off) engine reproduces the exact M1 population law, and a wrong law fails the same test.
- The accounting identity holds at every step; no fill occurs through the opposite touch; queue position only improves until a reprice, and a reprice goes to the back.
- Fixed seeds give byte-identical fill sequences; worker count does not change results.
- Shapley values sum to the total gap; the holdout is never replayed by M3, and M4 can touch it once, with a ledger.

## Limitations

A single LOBSTER day per symbol. A3 identification rests on extrapolating the depth response. The reference is a policy-class optimum, not a global optimum. Zero own impact. Virtual fills. The M1 claim covers the declared discrete law, not the authors' unpublished code.

[Decisions](docs/DECISIONS.md) · [State](STATE.md) · [Pre-registration draft](docs/PREREGISTRATION.draft.md) · [Benchmark a strategy](benchmarks/README.md)
