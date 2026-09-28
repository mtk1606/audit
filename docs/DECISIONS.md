# Decisions

## 2026-09-18 Approved initial scope and representation
Context: User approved the M0 plan in this chat.
Decision: Executable prices use integer ticks; timestamps use integer nanoseconds. Derived analytical prices may use floating point with documented units. M0 may proceed without the human-owned golden table and derivation; M1 remains blocked on those inputs. Implement and test the collector here, but leave its real one-hour acceptance run to user hardware.
Status: Approved by the user's “Yes”. No threshold or acceptance criterion was changed.

## 2026-09-18 Bounded sample cannot independently reconstruct every snapshot
Context: PRD §6 M0 requires exact reconstruction at every message index for all five tickers. Proposed interface accepts an initial bounded BookSnapshot and the supplied event stream.
Problem: Official output documentation describes messages within the requested price range. The executed diagnostic finds a previously unseen positive-size boundary price in every sample. Even access to all previous supplied snapshots and the current message does not provide this price or its quantity before the current reference snapshot reveals it. Source acquisition was initially blocked by old URLs returning an application shell, but the official client linked a legacy php.lobsterdata.com host; that access issue is resolved.
Evidence: docs/evidence/source_audit.json records checksums and witness rows: AAPL 48, AMZN 133, GOOG 65, INTC 5, MSFT 8 (one-based CSV rows). No full-depth initial state is supplied by the bounded sample.
Options:
1. Explicit snapshot-assisted bounded replay. Import newly visible boundary state from the corresponding observed snapshot; separately test event-driven changes on observable levels. Retain exact output comparisons but label imported cells as supplied, not independently reconstructed. This changes the acceptance contract and requires an additional order-identity policy before queue simulation.
2. Obtain complete raw order-level events and a sufficient initial state, reconstruct independently, and use LOBSTER only as the reference. Stronger test, with additional data access and preprocessing requirements; free availability has not been verified.
Recommendation: Option 1 for M0's bounded LOBSTER adapter, with explicit provenance and coverage reporting. Do not claim full L3 order identity or independent all-cell reconstruction. Use a separately specified full L3 source for those claims.
Blocked on: User approval of the revised reconstruction acceptance contract or provision of adequate full-depth inputs.

## 2026-09-18 Canonical event schema omits documented source semantics
Context: PRD §5.3 EventType and M0 adapter.
Problem: The official LOBSTER specification includes type 6 cross trades and distinct halt/resume status codes; the PRD enum omits cross trades and its event fields contain no explicit halt status. Treating status price codes as executable prices or silently discarding valid source types would lose meaning. No type 6 or 7 events occurred in the five downloaded samples, so sample success alone would not test these cases.
Options:
1. Extend EventType with CROSS and add an explicit optional halt-status field, with source metadata for values that are not executable prices.
2. Keep the original canonical schema and reject sessions containing unsupported source semantics; document the narrower adapter support.
Recommendation: Option 1, with targeted source-format fixtures after approval.
Blocked on: Approval to extend the canonical schema rather than silently deviating from the PRD.

## 2026-09-18 Approved bounded reconstruction and event schema amendments
Context: User responded “Approved” to both requested amendments in this chat.
Decision: M0 may import explicitly identified boundary state from current reference snapshots while independently checking event-driven observable changes. EventType gains CROSS, and halt status is represented explicitly rather than as an executable price.
Status: Approved. Supersedes the blocked statuses of the two preceding decisions. It does not establish full L3 order identity or FIFO priority.

Implementation detail: LOBSTER price_ticks use its native USD 0.0001 quantum, including sub-cent hidden executions found in the actual samples. The canonical metadata makes the scale explicit. This is an exact source encoding, not a modification of the PRD's later simulator quote increment. No M1 parameter has been populated.

Implementation detail: Python 3.11-compatible NumPy is constrained below 2.4; the complete environment is pinned in uv.lock. The first resolved NumPy exposed Python 3.12-only stub syntax to the Python 3.11 mypy target. This was a dependency compatibility issue, not a scientific or test-criterion change.

## 2026-09-18 Non-integral nanosecond source timestamps
Context: M0 clean-commit validation against all five official level-10 samples.
Problem: The canonical contract requires integer nanoseconds and forbids implicit data repairs. Ten raw timestamps have nonzero sub-nanosecond remainders: AMZN 2, INTC 5, MSFT 3. Each is 0.004 ns from the nearest integer ns. AAPL and GOOG have none. The validator correctly stops rather than truncating or rounding. Serialization noise is a hypothesis, not a verified cause.
Evidence: docs/evidence/m0 contains all five validation manifests, timestamp_precision.json, and its diagnostic manifest. The diagnostic computes differences only; it does not modify input or normalize timestamps.
Options:
1. Approve explicit Decimal-based nearest-nanosecond normalization (ROUND_HALF_EVEN), preserving original source strings and exact deltas in provenance, counting adjusted records and timestamp collisions, and retaining source row order. This sacrifices sub-nanosecond literal precision and must appear in config and manifests. Strict mode should remain available and its rejection test should remain unchanged.
2. Retain strict integer-nanosecond parsing and obtain provider-corrected inputs with verified provenance. This preserves the current contract but requires new source data.
3. Adopt an exact finer-resolution or rational timestamp schema throughout the project. This preserves literal precision but changes the PRD's core types and downstream interfaces.
Recommendation: Option 1, subject to user approval; do not infer a scientific tolerance threshold from these ten records. No rounding policy has been implemented or activated.
Blocked on: Approval of the exact timestamp-normalization policy or provision of corrected inputs. The general instruction to continue was used to finish verification and packaging, not to silently relax this data contract.

## 2026-09-19 Timestamp normalization approved
Context: The user approved explicit nearest-nanosecond normalization and requested concise professional writing without em dashes.
Decision: Add the nearest_ns policy using Decimal and ROUND_HALF_EVEN. Preserve each original timestamp and signed adjustment. Count adjusted records and newly merged timestamps; preserve source row order and reject source clock reversals even when rounded timestamps tie. Strict mode and its original rejection tests remain unchanged.
Configuration: The sample config opts into nearest_ns. The decoder and CLI defaults remain strict. Every run records the resolved policy and adjustment provenance.
Status: Approved and implemented. Supersedes the timestamp policy blocker above. Real sample verification follows this commit.
Presentation: Use a concise README, a compact evidence table, and separate operating instructions. Preserve original supplied specifications as source documents.

## 2026-09-19 Timestamp policy verified
All five clean-commit validation runs pass. Ten adjustments were recorded, each 0.004 ns in magnitude, with zero newly merged timestamps. Evidence is preserved in docs/evidence/m0-normalization. The timestamp blocker is resolved under the approved policy. The live collector acceptance item remains open.

## 2026-09-22 M0 accepted; implementation authority expanded
Context: The user explicitly accepted M0 and directed the move to M1, then
explicitly overrode the build instructions for the derivation and remaining work.
Decision: Record M0 as user-accepted with the live collector evidence still absent.
Author the derivation and choose explicit implementation and statistical conventions
without another approval pause. Do not represent missing evidence as a passing test.
The supplied golden table is copied byte-for-byte and its human-verification flag
remains false. No holdout data is accessed.

## 2026-09-22 Working-paper experiment protocol
Context: The attached source is dated October 5, 2006, not the 2008 publication.
Decision made before the first full run: seed 20260922, 1000 paths per strategy
and case, 2000 pathwise percentile bootstrap resamples, pointwise 95% intervals,
sample standard deviations with ddof=1. Independent SeedSequence children for
each strategy/case simulation, bootstrap and variance-ratio bootstrap. No seed
search and no tuning against target values. The ratio is symmetric profit
variance divided by inventory-strategy profit variance; the PRD's 10% tolerance
is retained. The default comparison treats source point estimates as targets,
without claiming to know uncertainty from the paper's unavailable raw paths.
Primary case: equation 3.18 spread and strict Bernoulli probability validity.
Diagnostic cases: equation spread with explicit probability saturation, and
constant liquidity spread with explicit saturation. Diagnostics cannot satisfy
primary acceptance. Profit is terminal cash plus marked inventory, less initial
marked wealth. Fills use old quotes before the independent binary mid move.
Continuous model prices and time use floating-point arithmetic in M1 only;
integer market-data and future execution interfaces remain unchanged.
Source ambiguities: table spreads omit the risk term; side dependence and seeds
are unspecified; lambda*dt can exceed one. Any failed replication remains a
reported failure. The 2008 published-version claim is withheld.

## 2026-09-22 M1 experiment outcome
The fixed protocol ran from clean commit 2b75c0b and exited 1 with status
not_reproduced. Primary inventory runs at gamma 0.1 and 0.5 encounter invalid
Bernoulli probabilities. The gamma 0.01 primary comparison also misses targets.
Neither diagnostic interpretation satisfies all numerical checks. Preserve all
results in docs/evidence/m1/run. M1 remains in progress; no M2 implementation or
verified-replication publication follows from these results. A source-faithful
resolution requires stronger evidence about the numerical procedure, not tuning
the simulator to the target table.

## 2026-09-22 Published paper supplied and benchmark clarified
The user supplied HighFrequencyTrading.pdf and as2008_table_qf2008.json. The PDF
is the published Quantitative Finance 8(3) article, pages 217-224, DOI
10.1080/14697680701381228. The agent visually checked all entries against printed
pages 222-223; the JSON matches. Preserve both source tables unchanged and retain
verified_by_human=false. The published source supersedes the working-paper
interpretation for current M1 acceptance, without erasing earlier evidence.

The published symmetric benchmark uses the average spread over the horizon,
not the inventory strategy's instantaneous spread. Implement its continuous
average gamma*sigma^2*T/2 + 2*log1p(gamma/k)/gamma. This matches the tables' rounded
average spreads. A discrete left-endpoint average differs by gamma*sigma^2*dt/2;
we use the continuous average as an explicit integration convention, not fitted
rounded table values. Inventory quotes retain the full time-dependent formula.
Table 3 uses gamma=1, not the working paper's gamma=0.5. All profit and inventory
targets now come directly from the separately preserved published JSON.

Before the published run: retain root seed 20260922, allocate independent streams
under namespace (2008,), 1000 paths, 2000 bootstrap repetitions and unchanged
acceptance tolerances. Run strict and explicitly saturated cases only; constant
liquidity-spread diagnostics are unnecessary now that the source clarifies the
benchmark. Saturated cases remain diagnostic and cannot satisfy primary acceptance.
The published text still does not specify overflow handling or bid/ask dependence.

## 2026-09-22 Published run outcome
Clean source commit 60542eb produced the published comparison. Strict Table 2
passes all metrics and the ratio criterion. Strict Tables 1 and 3 fail on invalid
probabilities. Their capped diagnostic realizations pass all numerical checks.
The independent capped Table 2 realization has no probability exceedances and
passes all eight metric intervals, but its variance ratio differs by 14.3%, above
the unchanged 10% threshold. Do not combine passing cases from different variants.
The source-version and benchmark-definition blockers are resolved; probability
handling remains unspecified. Overall M1 acceptance is incomplete.

## 2026-09-22 Independent moment audit
Continue within M1. Add a deterministic inventory-state probability and P&L-moment
recurrence for the existing declared discrete law, with no inventory cutoff and no
random seed. Independently check its symmetric case using closed-form moments and
small exhaustive state paths. The analytical recurrence must not reuse simulation
quotes or accounting. Do not use it to infer author intent or replace the original
Monte Carlo acceptance contract. Its results are population moments, so Monte Carlo
confidence intervals are not applicable to the deterministic calculation itself.

The author-maintained NYU papers index and Cornell publication links were inspected.
The relevant entries point to paper PDFs; no original simulation code or overflow
clarification was located in these entries or the targeted searches. This is not
proof that author code does not exist. Third-party replication code is not treated
as the authors' procedure and was not copied.

## 2026-09-28 M1 bounded sensitivity protocol (declared before computation)
Context: PRD M1 acceptance; STATE.md next step; user instruction to complete the
project. The published text leaves the probability rule for lambda*dt > 1 open.
Problem: the existing contract compares paper point values against intervals
from one seeded simulation. That test mixes our Monte Carlo noise with the
paper's and can reject a correct law (recorded SUSPECT). The population law is
already computable exactly (docs/reports/M1-moments.md).
Protocol, fixed now and not changed after results are seen:
- Probability rules: strict (lambda*dt, invalid above 1), saturate
  (min(lambda*dt, 1)), poisson (1 - exp(-lambda*dt): probability of at least one
  Poisson arrival in dt, one unit filled). Bid and ask independent; fills at old
  quotes before the binary mid move. No other rule is added after results.
- Time steps: dt in {0.005 (paper), 0.0025, 0.001}. dt != 0.005 is a
  discretisation-sensitivity check only, never an acceptance candidate.
- Statistic: for each table, strategy and metric (profit mean, profit SD,
  final inventory mean, final inventory SD) z = (paper - population) / SE, where
  SE is the paper's own sampling error at n=1000 under the declared law: SD/sqrt(n)
  for means, SD*sqrt((kurtosis-1)/(4n)) for SDs (delta method, exact population
  kurtosis from a fourth-moment recurrence), plus the variance of uniform
  rounding to the printed decimal. Variance ratio: z on log ratio with
  var = (kurt_sym - 1)/n + (kurt_inv - 1)/n + rounding term.
- Family: 3 tables x 2 strategies x 4 metrics + 3 ratios = 27 tests. Decision
  threshold: two-sided Bonferroni alpha 0.05, |z| <= Phi^-1(1 - 0.05/54) = 3.11.
- A rule is "consistent with the published tables" at dt=0.005 when every one of
  the 27 tests passes. All rules and all z-scores are reported, pass or fail.
- This is proposed as an amended M1 acceptance test. The original criteria and
  their failed outcomes are preserved unchanged; the user decides whether to
  adopt the amendment.
Recommendation: adopt the amendment only if exactly the rules the data cannot
distinguish are reported together, and describe M1 as a replication of the
declared discrete law, not of the authors' unpublished code.

## 2026-09-28 Proceeding past the M1 gate (user instruction)
The build protocol makes M2 wait for user sign-off on M1. The user instructed
this session to complete and build the project. This breaks the verification
chain once, stated here and in chat. M1 is reported as "complete, qualified,
pending user adoption of the amended criterion" (docs/reports/M1-sensitivity.md);
nothing downstream depends on the M1 printed numbers except through the
(off, off, off) reduction test, which uses the exact population law.

## 2026-09-28 M2 implementation decisions
- Data access: php.lobsterdata.com is denied by this environment's network
  policy (proxy 403). All M2/M3 code is exercised on a synthetic L3 generator
  (src/asaudit/sim/synthetic.py) with known mechanisms, per PRD 9's synthetic
  fixture allowance. Every number from it is labelled fixture output.
- FillModel receives a row range over a columnar ReplaySession plus a
  StepContext (mid, segment bounds, competition), not LOBEvent objects: same
  semantics, no per-event object allocation. MarketState gains `mid` and an
  optional `book` because the M1 reduction source has no book.
- A2 as target minus embedded adverse selection: Poisson fills embed none, queue
  fills on replayed flow embed the observed markout. A2 on + Poisson: charge the
  calibrated conditional mean adverse move. A2 off + queue: credit it back.
  Conditional mean, not a draw: same expectation, lower variance. Horizon is a
  config value (default 1 s); valuing a fill at a fixed horizon is an
  approximation to holding-period exposure.
- A3 acts through the ahead share of cancellations at our level, scaled by
  ((D+v)/D)^(e_cancel-1). Joins only arrive behind us, so e_join is reported
  but has no fill channel. Under Poisson fills there is no queue, so A3 has no
  channel; exact Shapley assigns any A1 x A3 interaction explicitly.
- Hidden executions do not interact with the visible queue (conservative).
- Resting orders at or through the opposite touch are suspended, not filled.
- Quotes beyond visible depth are withheld and counted (withheld_quotes).
- Seeds: one generator per (session, strategy), shared by all grid configs and
  cancel policies: common random numbers, a paired design for Shapley
  differences. Sessions use independent SeedSequence children.
- Elasticity intervals default to 50 ms: 1 s intervals attenuate both
  elasticities by about half on the fixture (stale depth regressor). Cancel
  elasticity is biased low by about 0.35 against the generator's per-order
  exponent, because order counts scale sub-linearly with depth; tests assert
  comparative statics for it, and recovery within 0.2 only for joins.
- Performance: 88.5k events, 36k 100 ms steps in 3.6 s single core on the
  fixture. Projected LOBSTER session (400k messages, 234k steps) about 21 s
  against the 30 s budget; not yet measured on real data. No numba.

## 2026-09-28 Invalidated fixture run (symbol collision)
The first fixture ablation (run 20260928T180309..._afff7daf4f) is invalid: the
synthetic generator stamped every session with symbol "SYN", so the five
sessions collided on (symbol, episode) keys and overwrote each other in the
attribution lookup. Fixed by passing the symbol through; load_sessions now
rejects duplicate symbols, and the pipeline test asserts per-symbol separation.
That run's output is discarded, not reported.
