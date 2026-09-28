// AS quote explorer: the published equations with the paper's parameters.
// Same formulas as src/asaudit/strategy/avellaneda_stoikov.py (equations 29-30).
import { s, svgRoot, linear, ticks, responsive, fmt } from "./svg";

export interface ASParams {
  s0: number;
  sigma: number;
  k: number;
  A: number;
  dt: number;
}

export interface Quotes {
  reservation: number;
  spread: number;
  bid: number;
  ask: number;
  deltaBid: number;
  deltaAsk: number;
  rawBid: number; // lambda(delta_b) * dt, not capped
  rawAsk: number;
}

export function asQuotes(p: ASParams, q: number, tau: number, gamma: number): Quotes {
  const risk = gamma * p.sigma ** 2 * tau;
  const reservation = p.s0 - q * risk;
  const spread = risk + (2 / gamma) * Math.log1p(gamma / p.k);
  const bid = reservation - spread / 2;
  const ask = reservation + spread / 2;
  const deltaBid = p.s0 - bid;
  const deltaAsk = ask - p.s0;
  const raw = (d: number) => p.A * Math.exp(-p.k * d) * p.dt;
  return { reservation, spread, bid, ask, deltaBid, deltaAsk, rawBid: raw(deltaBid), rawAsk: raw(deltaAsk) };
}

function probText(raw: number): string {
  if (raw > 1) return `${raw >= 100 ? Math.round(raw).toLocaleString("en-US") : fmt(raw, 2)}: above 100%, impossible`;
  return raw < 0.001 ? raw.toExponential(1) : fmt(raw, 3);
}

export function mountQuotes(root: HTMLElement, params: ASParams): void {
  const qIn = root.querySelector<HTMLInputElement>("#as-q");
  const tIn = root.querySelector<HTMLInputElement>("#as-tau");
  const qOut = root.querySelector<HTMLOutputElement>("#as-q-out");
  const tOut = root.querySelector<HTMLOutputElement>("#as-tau-out");
  const gGroup = root.querySelector<HTMLElement>("#as-gamma");
  const host = root.querySelector<HTMLElement>("#quotes-svg");
  const readout = root.querySelector<HTMLElement>("#quotes-readout");
  const takeaway = root.querySelector<HTMLElement>("#quotes-takeaway");
  if (!qIn || !tIn || !qOut || !tOut || !gGroup || !host || !readout || !takeaway) {
    throw new Error("quote figure markup missing");
  }
  let gamma = 0.1;
  let width = 680;

  const draw = () => {
    const q = Number(qIn.value);
    const tau = Number(tIn.value);
    qOut.value = q > 0 ? `+${q}` : String(q);
    tOut.value = tau.toFixed(2);
    const r = asQuotes(params, q, tau, gamma);

    const pts = [params.s0, r.reservation, r.bid, r.ask];
    const lo = Math.min(...pts);
    const hi = Math.max(...pts);
    const pad = Math.max(1, (hi - lo) * 0.12);
    const H = 110;
    const x = linear(lo - pad, hi + pad, 16, width - 16);
    const svg = svgRoot(width, H, `Bid ${fmt(r.bid)}, ask ${fmt(r.ask)}, reservation price ${fmt(r.reservation)}, mid 100`);
    const axisY = 70;
    svg.append(s("line", { x1: 16, x2: width - 16, y1: axisY, y2: axisY, stroke: "var(--rule-strong)" }));
    for (const t of ticks(lo - pad, hi + pad, width < 520 ? 4 : 7)) {
      svg.append(
        s("line", { x1: x(t), x2: x(t), y1: axisY, y2: axisY + 5, stroke: "var(--rule-strong)" }),
        s("text", { x: x(t), y: axisY + 19, "text-anchor": "middle", "font-size": 11, class: "mono-t", fill: "var(--muted)" }, [String(t)]),
      );
    }
    // Spread band between the quotes.
    svg.append(s("rect", { x: x(r.bid), y: axisY - 16, width: Math.max(1, x(r.ask) - x(r.bid)), height: 10, fill: "var(--band)" }));
    const mark = (v: number, color: string, label: string, above: number, anchor: "start" | "middle" | "end") => {
      svg.append(
        s("line", { x1: x(v), x2: x(v), y1: axisY - 20, y2: axisY, stroke: color, "stroke-width": 2 }),
        s("text", { x: x(v), y: axisY - 26 - above, "text-anchor": anchor, "font-size": 12, fill: "var(--ink)" }, [label]),
      );
    };
    mark(params.s0, "var(--ink)", "Mid 100", 18, "middle");
    const close = Math.abs(x(r.reservation) - x(params.s0)) < 60;
    mark(r.reservation, "var(--muted)", `Reservation ${fmt(r.reservation)}`, close ? 0 : 18, close ? "start" : "middle");
    const bidLeft = x(r.bid) < x(r.ask);
    mark(r.bid, "var(--accent)", `Buy ${fmt(r.bid)}`, 0, bidLeft ? "end" : "start");
    mark(r.ask, "var(--ask)", `Sell ${fmt(r.ask)}`, 0, bidLeft ? "start" : "end");
    host.replaceChildren(svg);

    readout.innerHTML = "";
    const cells: [string, string][] = [
      ["Total spread", fmt(r.spread, 3)],
      ["Buy quote distance from mid", fmt(r.deltaBid, 3)],
      ["Sell quote distance from mid", fmt(r.deltaAsk, 3)],
      ["Buy quote: fill chance per step", probText(r.rawBid)],
      ["Sell quote: fill chance per step", probText(r.rawAsk)],
    ];
    for (const [k, v] of cells) {
      const d = document.createElement("div");
      const kk = document.createElement("span");
      kk.className = "k";
      kk.textContent = k;
      const vv = document.createElement("span");
      vv.className = "v";
      vv.textContent = v;
      if (v.includes("impossible")) vv.style.color = "var(--ask)";
      d.append(kk, vv);
      readout.append(d);
    }
    const over = r.rawBid > 1 || r.rawAsk > 1;
    takeaway.textContent = over
      ? "The model now asks for a fill chance above 100% in a single step. The paper never says how its simulation handled this."
      : q === 0
        ? "With no inventory, the quotes sit symmetrically around the mid-price."
        : q > 0
          ? "Long inventory pulls both quotes down, so selling becomes more likely than buying."
          : "Short inventory pushes both quotes up, so buying becomes more likely than selling.";
  };

  for (const btn of gGroup.querySelectorAll<HTMLButtonElement>("button[data-gamma]")) {
    btn.addEventListener("click", () => {
      gamma = Number(btn.dataset.gamma);
      for (const b of gGroup.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === btn));
      draw();
    });
  }
  qIn.addEventListener("input", draw);
  tIn.addEventListener("input", draw);
  responsive(host, (w) => {
    width = Math.min(w, 900);
    draw();
  });
}
