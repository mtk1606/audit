# M4 correction: derivation (DRAFT for owner review)

> Agent-written. `docs/DERIVATION.md` is owner-maintained, so this extension is
> kept separate until the owner reviews it and merges it in. The implementation
> is `src/asaudit/strategy/corrected.py`.

## Result in one line

Each side quotes the tick-grid price that maximises

$$
\lambda(\delta)\,\pi\big(Q(\delta)\big)\;\frac{1-e^{-\gamma(\delta-c-\beta(\delta))}}{\gamma},
\qquad
c_b=\gamma\sigma^2\tau\,(q+\tfrac12),\quad c_a=\gamma\sigma^2\tau\,(\tfrac12-q),
$$

where $\pi(Q)$ is the fitted probability of a fill given queue position $Q$ at
that price, and $\beta$ is the calibrated expected adverse mid move after a fill.
With $\pi\equiv1$ and $\beta=0$ this reproduces AS exactly (section 2). What we
obtained is **semi-analytic**: a closed-form objective maximised numerically over
a finite price grid. It is not a closed-form quote.

## 1. Setup

Notation follows `docs/DERIVATION.md`: $u(s,x,q,t)=-\exp(-\gamma(x+\theta(s,q,t)))$.
Two changes to the HJB:

1. **Queue-conditional intensity.** A bid at distance $\delta$ joins a queue of
   size $Q(\delta)$: zero when it improves the touch, otherwise the visible depth
   at that price. Its fill intensity is $\lambda(\delta,Q)=A e^{-k\delta}\pi(Q)$.
   Here $\pi$ is the logistic fill probability from `calibration/queue_fill.py`,
   used as a multiplicative thinning of the AS intensity. This is an
   approximation: $\pi$ is a probability within a horizon, not a rate.
2. **Informed flow.** When our bid fills, the mid jumps by $-\beta_b$ in
   expectation, and our ask fill brings $+\beta_a$, with $\beta_b,\beta_a\ge0$
   measured as adverse moves (`calibration/adverse.py`). Only the filled unit is
   revalued: the exogenous mid path already carries the move for existing
   inventory in replay. This matches how the engine books A2.

## 2. The bid problem and the AS limit

A bid fill changes wealth by $-(s-\delta_b)$ and inventory by $+1$, then the
unit is marked at $s-\beta_b$. Its value is $\delta_b-\beta_b$. In the
exponential transformation, the bid term of the HJB is

$$
\sup_{\delta_b}\;\frac{\lambda_b(\delta_b)}{\gamma}\Big(1-e^{-\gamma(\delta_b-\beta_b-[\theta(q)-\theta(q+1)])}\Big).
$$

Under the AS frozen-inventory approximation,
$\theta(q)-\theta(q+1)=\gamma\sigma^2\tau(q+\tfrac12)=c_b$. For
$\lambda=Ae^{-k\delta}$ and $\beta=0$, the first-order condition is
$-k(1-e^{-\gamma(\delta-c)})+\gamma e^{-\gamma(\delta-c)}=0$. That gives
$\delta_b^*=c_b+\tfrac1\gamma\ln(1+\tfrac\gamma k)$, the AS bid distance
$(s-r)+\Delta/2$. `tests/unit/test_corrected.py` checks that the grid maximiser
neighbours this value.

## 3. What each term does

- **Adverse term.** With constant $\beta$ the optimum shifts one-for-one:
  $\delta_b^*=c_b+\beta_b+\tfrac1\gamma\ln(1+\tfrac\gamma k)$. In
  reservation-price form:
  $r=s-q\gamma\sigma^2\tau+(\beta_a-\beta_b)/2$, with half-spread widened by
  $(\beta_a+\beta_b)/2$. The PRD sketched $-(\beta_a-\beta_b)/2$ with signed
  expected moves. With adverse magnitudes as defined here, the sign is $+$:
  the side with more adverse selection is quoted further away. The width term
  agrees with the PRD sketch.
- **Queue term.** Where $\pi(Q(\delta))$ varies smoothly, it acts as an
  effective decay $k_{\text{eff}}=k-\partial_\delta\ln\pi$. The optimal
  liquidity term becomes $\tfrac1\gamma\ln(1+\gamma/k_{\text{eff}})$. On a real
  book $Q(\delta)$ jumps between levels (zero inside the spread, then touch
  depth, then deeper levels), so the rule compares discrete candidates rather
  than differentiating.
- A multiplicative constant in $\lambda$ (such as $A$) does not move the
  maximiser. The queue term matters through how $\pi$ changes across prices,
  not through its level.

## 4. Assumptions to state in the writeup

- Frozen-inventory approximation, as in AS.
- $\pi$ is a within-horizon probability used as an intensity multiplier.
- $\beta$ is a conditional mean at a fixed horizon (1 s), not a jump law.
- Zero own impact. Our order does not change $Q$ for others, beyond the A3
  channel in the simulator.
- Myopic per-step optimisation: the rule re-optimises every batch, with no
  value for queue position carried over between steps.
