# Independent discrete-model verification

An independent finite-state calculation now provides population profit and inventory moments for the declared capped-Bernoulli experiment. This verifies the implemented model more strongly than comparing one simulation seed with a published table. It does not establish which numerical convention the authors used.

## Derivation

Let P(q), M(q) and V(q) be probability mass, probability-weighted accumulated profit, and probability-weighted squared profit before a step. For independent bid and ask indicators b,a, transition probability w, next inventory q'=q+b-a, and spread capture c=b*delta_b+a*delta_a, the update is:

```text
P_next(q') += w P(q)
M_next(q') += w [M(q) + c P(q)]
V_next(q') += w [V(q) + 2 c M(q) + (c^2 + q'^2 sigma^2 dt) P(q)]
```

The independent mid increment has zero mean and variance sigma^2 dt, after fills. This eliminates the need to enumerate price paths. Quotes depend on inventory and time through their distances from mid, so inventory is a sufficient state for this recurrence. All reachable inventory states are propagated, without a cutoff. Exact zeros and floating-point underflow can vanish; there is no probability pruning threshold. Total mass is checked.

For constant symmetric half-spread h and independent side probability p, after N steps:

```text
E[profit] = 2 h N p
Var(q_N) = 2 N p (1-p)
Var(profit) = 2 h^2 N p (1-p)
              + sigma^2 dt [N q0^2 + p (1-p) N (N+1)]
```

The first variance term is spread-capture variability. The second is inventory exposure to the price moves after each step. Initial marked wealth is subtracted from profit. These identities supply a second independent check of the finite-state calculation.

## Population moments

These are deterministic mathematical expectations under the declared discrete model, evaluated in floating-point arithmetic. They have no Monte Carlo confidence interval. They are not observed market returns.

| Table | Strategy | Profit mean: model / paper | Profit SD: model / paper | Inventory SD: model / paper | Expected capped side-steps per path |
|---|---|---|---|---|---|
| 1 | inventory | 64.8925 / 65.0 | 6.5432 / 6.6 | 2.9268 / 2.9 | 0.033815 |
| 1 | symmetric | 68.2282 / 68.4 | 13.4573 / 12.7 | 8.4017 / 8.4 | 0 |
| 2 | inventory | 68.3996 / 68.6 | 8.9606 / 8.7 | 5.2125 / 5.1 | 2.6476e-33 |
| 2 | symmetric | 68.6662 / 68.8 | 13.6776 / 12.8 | 8.7119 / 8.7 | 0 |
| 3 | inventory | 31.4545 / 31.4 | 4.8379 / 5.0 | 1.6414 / 1.7 | 10.35 |
| 3 | symmetric | 43.8690 / 44.0 | 10.7515 / 11.0 | 5.1893 / 5.1 | 0 |

All population mean terminal inventories are zero to numerical precision for these zero-inventory starts, as required by bid/ask symmetry. The source table means are finite-sample outcomes and need not be exactly zero.

The gamma=0.01 model has an extremely small but nonzero expected exceedance count. A sampled run finding zero exceedances does not prove that its Bernoulli approximation is valid on every reachable state. Strict Monte Carlo success and strict global reachability are different checks.

## Validation

- Six new tests cover exhaustive two-step inventory paths, nonzero initial inventory, saturated transitions, invalid probabilities, the symmetric closed form, and every equal-probability two-step path through the Monte Carlo engine.
- No simulation quoting helper or accounting function is reused by the moment recurrence. This reduces shared-implementation blind spots.
- Across the three published symmetric cases, recurrence and closed form differ by less than 6.2e-11 across the reported moments.
- 72 tests pass; lint, formatting and strict typing pass.

[Full moments](../evidence/m1-moments/run/moments.json) and [manifest](../evidence/m1-moments/run/manifest.json) record the deterministic run from clean commit 76bc166 and the exact prior experiment configurations.

## Source search

Targeted searches and inspection of [Avellaneda's NYU papers index](https://math.nyu.edu/inmemoriam/avellaneda/Papers.html) and [Stoikov's Cornell publications page](https://people.orie.cornell.edu/sfs33/publications.html) located paper links, but no original simulation code or overflow clarification in those entries. This is a limited search result, not proof that original code does not exist. Third-party implementations were not copied or used to establish author intent. No messages were sent to anyone.

## What this establishes

The discrete model has been independently verified against deterministic probability and accounting calculations. The source tables show substantial but incomplete agreement with that law. A successful seeded comparison does not prove the model exactly matches the authors' simulation, and a failed pointwise comparison alone does not prove an implementation defect. The original Monte Carlo evidence and acceptance status remain unchanged.

**M1 remains in progress.** The remaining issue is the relationship between a declared numerical convention and the paper's unspecified implementation. The defensible current claim is an auditable numerical study with explicit assumptions. Do not publish it as an exact reproduction or move to M2 on an unqualified success claim.

## Reproduce

```bash
uv run asaudit audit-moments
```

This reads the committed published-run configurations and writes a new manifest and moments JSON. No random numbers or additional market data are used.
