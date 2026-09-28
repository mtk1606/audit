# M1: bounded sensitivity study and completion recommendation

**Result: every printed value in Tables 1-3 is consistent with one declared discrete law, and inconsistent with the two alternatives tested.** Under capped Bernoulli fills (`min(lambda*dt, 1)`) at the paper's dt = 0.005, all 27 pre-declared tests pass (max |z| = 1.88, threshold 3.11). The Poisson rule `1 - exp(-lambda*dt)` fails 7 of 27 (max |z| = 38.5). Every rule fails at smaller dt. The strict rule is undefined for all three inventory strategies.

This replicates the declared law, not the authors' unpublished code. The original acceptance contract and its failed outcomes are unchanged in [M1-qf2008.md](M1-qf2008.md).

## Why a different test

The original contract checks whether each printed value lies inside a bootstrap interval from one seeded run of ours. That compares two noisy samples as if one were exact, and it can reject a correct law (recorded SUSPECT). The population law is computable exactly ([M1-moments.md](M1-moments.md)), so the right question is narrower: *is each printed value a plausible n = 1000 sample from this law?*

For each cell, z = (printed - population) / SE. SE is the paper's own sampling error at n = 1000, from exact population moments:

| Metric | Sampling variance |
|---|---|
| Mean | variance / n |
| SD | variance * (kurtosis - 1) / (4n), delta method |
| Log variance ratio | (kurt_sym - 1)/n + (kurt_inv - 1)/n |

The variance of uniform rounding to the printed decimal is added to each. Kurtosis comes from a new fourth-moment recurrence, verified against exhaustive path enumeration (`tests/test_m1_sensitivity.py`). Family: 24 cells + 3 ratios = 27 tests, Bonferroni two-sided alpha 0.05, |z| <= 3.11. The protocol, rules and dt grid were committed in `docs/DECISIONS.md` (6adb9a3) before any number was computed. No seed is involved.

## Results at the paper's dt = 0.005

Cells show printed / population (z).

| Table | Strategy | Profit mean | Profit SD | Final q mean | Final q SD |
|---|---|---|---|---|---|
| 1, gamma 0.1 | inventory | 65.0 / 64.89 (+0.51) | 6.6 / 6.54 (+0.38) | 0.08 / 0 (+0.86) | 2.9 / 2.93 (-0.38) |
| 1 | symmetric | 68.4 / 68.23 (+0.40) | 12.7 / 13.46 (-1.69) | 0.26 / 0 (+0.98) | 8.4 / 8.40 (-0.01) |
| 2, gamma 0.01 | inventory | 68.6 / 68.40 (+0.70) | 8.7 / 8.96 (-1.12) | 0.12 / 0 (+0.73) | 5.1 / 5.21 (-0.94) |
| 2 | symmetric | 68.8 / 68.67 (+0.31) | 12.8 / 13.68 (-1.88) | 0.09 / 0 (+0.33) | 8.7 / 8.71 (-0.06) |
| 3, gamma 1 | inventory | 31.4 / 31.45 (-0.35) | 5.0 / 4.84 (+1.42) | 0.02 / 0 (+0.38) | 1.7 / 1.64 (+1.26) |
| 3 | symmetric | 44.0 / 43.87 (+0.38) | 11.0 / 10.75 (+0.85) | 0.00 / 0 (0.00) | 5.1 / 5.19 (-0.74) |

| Table | Printed variance ratio | Population ratio | Relative deviation | z (log ratio) |
|---|---:|---:|---:|---:|
| 1 | 3.70 | 4.23 | 14.2% | -1.64 |
| 2 | 2.17 | 2.33 | 7.6% | -0.86 |
| 3 | 4.84 | 4.94 | 2.0% | -0.28 |

| Rule | dt | Tests run | Failures | Max abs z |
|---|---:|---:|---:|---:|
| strict | 0.005 | 12 | 0 (15 undefined) | 1.88 |
| **saturate** | **0.005** | **27** | **0** | **1.88** |
| poisson | 0.005 | 27 | 7 | 38.52 |
| saturate | 0.0025 | 27 | 6 | 4.24 |
| saturate | 0.001 | 27 | 11 | 5.90 |
| poisson | 0.001 | 27 | 13 | 10.94 |

## What this establishes

1. **The capped rule is the only tested rule the tables support.** The Poisson rule is not merely less accurate: it lowers expected profit by 3.5-12% (z up to 38), because 1 - exp(-x) < x lowers every fill probability (x = 0.4 gives 0.33). The saturate law matches without adjustment.
2. **The published numbers depend on the discretisation.** Halving dt raises every profit SD (Table 1 symmetric: 13.46 -> 14.41 -> 14.95 at dt 0.005, 0.0025, 0.001), because Bernoulli variance p(1-p) sits below its Poisson limit. The tables describe the dt = 0.005 discrete experiment, not the continuous-time model. This belongs in the limitations of any claim built on them.
3. **The PRD's 10% variance-ratio criterion is tighter than the paper's own noise.** The printed ratio has a sampling SE of about 8% in log terms, so a +/-10% band is about 1.2 SE wide. The true law would miss it often. Table 1's printed ratio is 14.2% from the population ratio, yet only 1.64 SE away. This explains the capped Table 2 realization that missed the band by 14.3%.
4. **Side dependence and update order are not separately identified.** Only independent sides with fills before the mid move were tested. The study does not rule out an alternative that happens to produce the same moments.

## Proposed amendment (user decision)

Replace the M1 acceptance rows with:

> Every printed mean, SD and variance ratio in Tables 1-3 lies within the Bonferroni-adjusted 95% sampling band of an n = 1000 estimate under the declared discrete law (capped Bernoulli, independent sides, dt = 0.005). The population moments are computed exactly and checked against exhaustive enumeration and an independent Monte Carlo run.

Recommended completion wording:

> M1 complete, qualified: the published AS 2008 tables are reproduced as a declared discrete law with capped fill probabilities. The authors did not specify that convention; it is identified because the Poisson alternative and finer time steps are rejected. This is not a verification of the original code.

If you do not adopt the amendment, M1 stays in progress under the original criteria. Nothing in this study changes the original outcome.

## Reproduce

```bash
uv run asaudit m1-sensitivity
```

Deterministic; about 5 minutes on one core. Evidence: [sensitivity.json](../evidence/m1-sensitivity/run/sensitivity.json), [manifest](../evidence/m1-sensitivity/run/manifest.json), clean commit e77692c.
