// Queue explainer. The mechanics are the project's rules, applied to example
// quantities: FIFO consumption at one price level (sim/fills/queue.py) and the
// three cancellation-attribution policies (PRD 4.3). Uniform shows the expected
// share, where the simulator draws Binomial(cancelled, ahead / depth).
import { s, svgRoot, responsive } from "./svg";

const MINE = 10;
const BEHIND = 12;
const CANCELLED = 8;
type Policy = "pessimistic" | "uniform" | "optimistic";

export function fillFromQueue(ahead: number, sell: number, mine = MINE): number {
  return Math.max(0, Math.min(mine, sell - ahead));
}

export function aheadAfterCancel(ahead: number, policy: Policy, cancelled = CANCELLED): number {
  if (policy === "pessimistic") return ahead;
  if (policy === "optimistic") return Math.max(0, ahead - Math.min(cancelled, ahead));
  const depth = ahead + BEHIND;
  return depth > 0 ? ahead - (cancelled * ahead) / depth : 0;
}

export function mountQueue(root: HTMLElement): void {
  const aheadInput = root.querySelector<HTMLInputElement>("#q-ahead");
  const sellInput = root.querySelector<HTMLInputElement>("#q-sell");
  const aheadOut = root.querySelector<HTMLOutputElement>("#q-ahead-out");
  const sellOut = root.querySelector<HTMLOutputElement>("#q-sell-out");
  const host = root.querySelector<HTMLElement>("#queue-svg");
  const outcome = root.querySelector<HTMLElement>("#queue-outcome");
  const policyGroup = root.querySelector<HTMLElement>("#q-policy");
  const policyNote = root.querySelector<HTMLElement>("#q-policy-note");
  if (!aheadInput || !sellInput || !aheadOut || !sellOut || !host || !outcome || !policyGroup || !policyNote) {
    throw new Error("queue figure markup missing");
  }
  let policy: Policy = "uniform";
  let width = 680;

  const draw = () => {
    const ahead = Number(aheadInput.value);
    const sell = Number(sellInput.value);
    aheadOut.value = String(ahead);
    sellOut.value = String(sell);
    const filled = fillFromQueue(ahead, sell);
    const total = 40 + MINE + BEHIND;
    const narrow = width < 520;
    const H = narrow ? 150 : 138;
    const left = 4;
    const right = width - 8;
    const x = (shares: number) => left + (shares / total) * (right - left);
    const barY = 58;
    const barH = 34;
    const svg = svgRoot(width, H, `Queue with ${ahead} shares ahead, your 10 shares, and a sell order of ${sell} shares`);

    // Sell order bracket, consumed from the front.
    const reach = Math.min(sell, ahead + MINE + BEHIND);
    if (sell > 0) {
      svg.append(
        s("path", {
          d: `M${x(0)},${barY - 10} V${barY - 18} H${x(reach)} V${barY - 10}`,
          fill: "none",
          stroke: "var(--ask)",
          "stroke-width": 1.5,
        }),
        s("text", { x: x(0), y: barY - 26, "font-size": 12, fill: "var(--ask)" }, [
          `Incoming sell order: ${sell} shares${sell > reach ? " (more than the whole level)" : ""}`,
        ]),
      );
    }
    // Ahead of you: one cell per share, served first.
    for (let i = 0; i < ahead; i++) {
      svg.append(
        s("rect", {
          x: x(i) + 0.6,
          y: barY,
          width: Math.max(0.5, x(i + 1) - x(i) - 1.2),
          height: barH,
          fill: i < sell ? "var(--rule-strong)" : "var(--rule)",
        }),
      );
    }
    // Your order.
    svg.append(
      s("rect", { x: x(ahead) + 0.6, y: barY, width: x(ahead + MINE) - x(ahead) - 1.2, height: barH, fill: "var(--accent-soft)", stroke: "var(--accent)", "stroke-width": 1.5 }),
    );
    if (filled > 0) {
      svg.append(
        s("rect", { x: x(ahead) + 0.6, y: barY, width: x(ahead + filled) - x(ahead) - 1.2, height: barH, fill: "var(--accent)" }),
      );
    }
    svg.append(
      s("text", { x: x(ahead + MINE / 2), y: barY + barH + 18, "text-anchor": "middle", "font-size": 12, "font-weight": 600, fill: "var(--ink)" }, ["You, 10 shares"]),
    );
    // Behind you.
    for (let i = 0; i < BEHIND; i++) {
      const at = ahead + MINE + i;
      svg.append(
        s("rect", { x: x(at) + 0.6, y: barY, width: Math.max(0.5, x(at + 1) - x(at) - 1.2), height: barH, fill: "var(--surface)", stroke: "var(--rule)", "stroke-width": 1 }),
      );
    }
    svg.append(
      s("text", { x: x(0), y: barY + barH + (narrow ? 36 : 18), "font-size": 11, fill: "var(--muted)" }, [
        narrow ? "← Front of the line, served first" : "Front of the line, served first",
      ]),
    );
    if (!narrow) {
      svg.append(
        s("text", { x: x(ahead + MINE + BEHIND), y: barY + barH + 18, "text-anchor": "end", "font-size": 11, fill: "var(--muted)" }, ["Joined after you"]),
      );
    }
    host.replaceChildren(svg);

    outcome.textContent =
      filled === 0
        ? sell <= ahead
          ? `The sell order is used up ${ahead - sell === 0 ? "exactly as it reaches you" : `${ahead - sell} shares before it reaches you`}. You trade nothing.`
          : ""
        : filled === MINE
          ? `The sell order clears the ${ahead} shares ahead of you and all 10 of yours.`
          : `The sell order clears the ${ahead} shares ahead of you, then ${filled} of your 10.`;

    const after = aheadAfterCancel(ahead, policy);
    const shown = Number.isInteger(after) ? String(after) : after.toFixed(1);
    policyNote.textContent =
      policy === "pessimistic"
        ? `If ${CANCELLED} shares cancel at your price and all were behind you, you still have ${ahead} ahead. This bound gives the fewest fills.`
        : policy === "optimistic"
          ? `If ${CANCELLED} shares cancel and all were ahead of you, ${shown} remain ahead. This bound gives the most fills.`
          : `If ${CANCELLED} shares cancel, spread in proportion to the queue, about ${shown} remain ahead of you on average.`;
  };

  for (const btn of policyGroup.querySelectorAll<HTMLButtonElement>("button[data-policy]")) {
    btn.addEventListener("click", () => {
      policy = btn.dataset.policy as Policy;
      for (const b of policyGroup.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === btn));
      draw();
    });
  }
  aheadInput.addEventListener("input", draw);
  sellInput.addEventListener("input", draw);
  responsive(host, (w) => {
    width = Math.min(w, 900);
    draw();
  });
}
