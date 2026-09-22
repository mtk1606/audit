# Avellaneda-Stoikov quoting equations

Source: the user-supplied *High-frequency trading in a limit order book*, Marco
Avellaneda and Sasha Stoikov, dated October 5, 2006. Equation numbers below refer
to that working paper. This document is an independently written derivation,
not evidence that the 2008 published version has been replicated.

## State and objective

Let cash be x, inventory q, mid-price s, remaining time tau = T - t, and
risk aversion gamma > 0. A bid fill buys one share: cash changes by -p_b and
inventory by +1. An ask fill sells one share: cash changes by +p_a and inventory
by -1. The mid obeys dS = sigma dW. There is no drift, fee, latency or queue.
Terminal wealth is X_T + q_T S_T; this marks inventory at mid without a
liquidation fee. This follows the objective in equation 3.1, although the tables
call their metric simply "Profit".

The objective is u(s,x,q,t) = sup E[-exp(-gamma (X_T + q_T S_T))]. Set
p_b = s - delta_b and p_a = s + delta_a. The HJB is

$$
0=u_t+\tfrac12\sigma^2u_{ss}
+\sup_{\delta_b}\lambda_b(\delta_b)
 [u(s,x-s+\delta_b,q+1,t)-u]
+\sup_{\delta_a}\lambda_a(\delta_a)
 [u(s,x+s+\delta_a,q-1,t)-u].
$$

The terminal condition is u(s,x,q,T) = -exp(-gamma(x+qs)). This fixes the
inventory and cash signs before taking any approximation.

## Exponential-utility transformation

Write u = -exp[-gamma(x + theta(s,q,t))]. Dividing the HJB by -gamma u,
which is positive, preserves each supremum. The continuous part becomes

$$
\theta_t+\tfrac12\sigma^2\theta_{ss}
-\tfrac12\gamma\sigma^2\theta_s^2.
$$

Define the marginal reservation prices directly by finite differences:

$$
r_b=\theta(s,q+1,t)-\theta(s,q,t),\qquad
r_a=\theta(s,q,t)-\theta(s,q-1,t).
$$

The bid jump term becomes lambda_b / gamma times
[1 - exp(-gamma(delta_b - s + r_b))]. The ask jump term becomes
lambda_a / gamma times [1 - exp(-gamma(delta_a + s - r_a))].

For lambda(delta) = A exp(-k delta), either maximization has the form
f(delta) = (A/gamma) exp(-k delta)[1-exp(-gamma(delta-c))].
Differentiation gives exp(-gamma(delta-c)) = k/(k+gamma), hence

$$
\delta_b=s-r_b+L,\qquad \delta_a=r_a-s+L,
\qquad L=\frac{\log(1+\gamma/k)}{\gamma}.
$$

For unrestricted real quote distances this stationary point is the maximum:
f tends to negative infinity as delta tends to negative infinity and tends
to zero from above as delta tends to positive infinity. Nonnegative-distance
constraints would change the optimizer. They are not silently imposed here.

## Frozen inventory approximation

If the inventory is held fixed until T, the Gaussian moment-generating function
in the terminal utility gives the certainty equivalent

$$
\theta_{\mathrm{frozen}}(s,q,t)
=qs-\tfrac12\gamma q^2\sigma^2(T-t).
$$

Its finite differences give

$$
r_b=s-\gamma\sigma^2(T-t)(q+\tfrac12),\qquad
r_a=s-\gamma\sigma^2(T-t)(q-\tfrac12).
$$

An additive term independent of q cancels in these differences. Substituting
these reservation prices into the exponential-intensity optimizer gives

$$
r=\frac{r_a+r_b}{2}=s-q\gamma\sigma^2(T-t),
$$

$$
w=\delta_a+\delta_b=\gamma\sigma^2(T-t)
+\frac{2}{\gamma}\log(1+\gamma/k),\qquad
p_b=r-w/2,\quad p_a=r+w/2.
$$

These match equations 3.17 and 3.18. The frozen-inventory certainty equivalent
is not the exact solution of the trading HJB. In particular, the optimized
arrival contribution generally depends on q. The paper connects the same
formula to a linearized arrival expansion. Its printed polynomial conventions
in equations 3.10-3.12 are not algebraically consistent as written: finite
differences of theta_0 + q theta_1 + q^2 theta_2 / 2 do not yield the displayed
reservation expressions. The direct finite-difference derivation above avoids
using that inconsistency as an implementation rule.

At q = 0 or t = T, r = s. For positive gamma, sigma and remaining time,
increasing q lowers both quotes. The spread increases with sigma and remaining
time. Using log(1+z) = z-z^2/2+O(z^3),

$$
w=\frac2k+\gamma\left(\sigma^2(T-t)-\frac1{k^2}\right)+O(\gamma^2).
$$

Thus w tends to 2/k, and r tends to s, as gamma tends to zero. The implementation
uses log1p and a separate exact gamma=0 branch.

## Discrete experiment and unresolved interpretation

The working paper uses 200 steps, binary mid increments of plus or minus
sigma sqrt(dt), and at most one fill per side per step. This is its stated
numerical approximation to the continuous model, not a Gaussian-increment or
continuous-time Poisson implementation. Both sides use the pre-step state.
Independent uniforms implement the bid and ask Bernoulli trials. The paper
does not specify their dependence or a random seed.

Cash changes at the old quotes, then the mid moves. The implementation verifies
cash + inventory * mid against an independent increment calculation each step:
spread capture at the old mid plus the new inventory times the mid change.
Profit subtracts initial marked wealth. Sample standard deviations use ddof=1;
the paper does not state a divisor.

The tables' spread entries match 2L rounded to two decimals, while equation
3.18 adds a time-dependent risk term. The text also describes the benchmark as
using the same spread. We therefore preserve equation 3.18 as the primary
specification and evaluate constant 2L only as a labelled sensitivity case.

The literal lambda*dt can exceed one. Strict runs stop at the first occurrence.
The additional saturated runs explicitly use min(lambda*dt, 1), count every
exceedance and report its largest raw value. This convention is not established
by the source and cannot count as primary replication acceptance.

The continuous model uses floating-point theoretical prices and model time in
this isolated experiment. Integer venue prices and nanosecond timestamps in the
M0 data interfaces are unchanged. Rounding to a venue grid would modify the
paper's experiment and is intentionally not introduced.

## Review status

Algebra checked through the HJB transformation and direct finite differences;
sign, boundary and risk-neutral behavior covered by automated tests. Source
tables checked visually against PDF pages 11-12 by the build agent. This is
not a human review or a verification of the published 2008 article.

## Published 2008 source update

The subsequently supplied published article, Quantitative Finance 8(3), 217-224,
DOI 10.1080/14697680701381228, uses the same final reservation and spread formulas
as equations 29 and 30. Its section 3.3 explicitly defines the symmetric benchmark
by the average spread over the time period. Thus the earlier working-paper
spread ambiguity is resolved for the published experiment:

$$
\bar w=\frac{1}{T}\int_0^T w(t)\,dt
=\frac{\gamma\sigma^2 T}{2}+\frac{2}{\gamma}\log(1+\gamma/k).
$$

The symmetric quotes are s minus/plus half this constant average. Inventory quotes
continue using r(t) and w(t). The published Table 3 uses gamma=1. A left-endpoint
discrete average would add gamma*sigma^2*dt/2; the experiment explicitly uses the
continuous average, consistent with the rounded table entries. The earlier
constant-liquidity-spread diagnostic is not used for the published source.

The published text does not resolve lambda*dt > 1. Strict and saturated runs remain
separate, with counts and failure outcomes preserved. The source change improves
numerical agreement but does not justify inferring the authors' overflow convention.
