# Pre-registration (DRAFT, not in force)

> This is an agent-written draft. It takes effect only when the project owner
> copies it to `PREREGISTRATION.md` at the repository root, edits it as they see
> fit, commits it and tags the commit (for example `prereg-v1`) **before any M3
> result on market data is computed**. After that, the file is not edited;
> amendments go in a dated appendix. Fixture runs on synthetic data are pipeline
> tests, not results, and do not break this ordering.

## 1. Thesis under test

The Avellaneda-Stoikov reservation price is systematically biased in the
presence of queue position and adverse selection. The bias is measurable and
decomposable by assumption. A corrected quoting rule recovers a quantifiable
fraction of the shortfall against a policy-class optimum.

## 2. Primary metric

`gap_bps = (PnL_PolicyClassOptimum - PnL_AS) / notional_traded_AS * 10_000`, per
out-of-sample episode. The reference policy class is `linear_skew`; `tabular_binned`
is a robustness check. The attribution target is
`gap_bps(A1, A2, A3 all on) - gap_bps(all off)`, decomposed by exact Shapley
values over the eight grid cells.

## 3. Data, splits and episodes

- LOBSTER sample, AMZN, AAPL, GOOG, INTC, MSFT, 2012-06-21, 10 levels, 09:30-16:00.
- Episodes of 300 s. Per symbol, in time order: calibration 40%, policy fit 30%,
  holdout 30%. The holdout is replayed once, for M4 only.
- Crypto L3 (Coinbase full channel) as an independent generalisation sample,
  when collected. It gets its own split, fixed before its data is examined.

## 4. Mechanisms and bounds

- Cancel attribution: `uniform` is the headline; `pessimistic` and `optimistic`
  bound it. If an axis changes sign between the bounds, no headline is
  reported for that axis; the bound interval is the result.
- Adverse-selection horizon 1 s. Latency 100 microseconds. Quote size 1 lot.
  Inventory cap 20 lots. Batch 100 ms.

## 5. Statistical tests

- Every headline: mean over episodes with a 95% stationary block bootstrap
  interval (Politis-White block length, 10,000 resamples) over time-ordered
  episodes.
- An axis attribution is called non-zero when its 95% interval excludes zero
  under `uniform` and the sign agrees under both bounds.
- Stability: sign agreement of each axis in at least 4 of 5 symbols, and
  identical rank ordering of |A1|, |A2|, |A3| in at least 3 of 5 symbols.
- Multiplicity: three axes, Bonferroni-adjusted two-sided alpha 0.05/3 for
  the "non-zero" call. Regime results are descriptive (no significance claims).

## 6. Regimes

Terciles of time-weighted spread, realised 1-minute volatility and top-of-book
depth, with edges per symbol over calibration and policy-fit episodes only.
Report axis marginals and the spread x volatility interaction; never the 27-cell
grid.

## 7. Order of reporting

A2 (adverse selection) is computed and reported first.

## 8. Negative results

If the corrections are small, or AS is within its bound interval of the
policy-class optimum, that result is published with the same prominence,
figure and detail as a positive one.

## 9. Known limitations fixed in advance

A single trading day per symbol in the LOBSTER sample. A3 identification
assumes depth response extrapolates to the counterfactual depth. The
reference is a policy-class optimum, not a global optimum. Zero own impact.
Fills are virtual.
