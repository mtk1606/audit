// Conceptual diagrams. They show structure, not data, and are labelled so.
import { s, svgRoot, responsive } from "./svg";

/** The 2^3 ablation grid as a cube; label bits are (A1, A2, A3). */
export function mountGrid(host: HTMLElement): void {
  responsive(host, (w) => {
    const width = Math.min(w, 520);
    const k = width / 420;
    const H = Math.round(330 * k);
    const svg = svgRoot(width, H, "Cube of eight configurations. 000 is the paper's world, 111 has queue position, adverse selection and competition all switched on.");
    const o = { x: 70 * k, y: 230 * k };
    const e1 = { x: 190 * k, y: 0 };
    const e2 = { x: 0, y: -135 * k };
    const e3 = { x: 85 * k, y: -60 * k };
    const P = (a: number, b: number, c: number) => ({
      x: o.x + a * e1.x + b * e2.x + c * e3.x,
      y: o.y + a * e1.y + b * e2.y + c * e3.y,
    });
    const verts: [number, number, number][] = [];
    for (const a of [0, 1]) for (const b of [0, 1]) for (const c of [0, 1]) verts.push([a, b, c]);
    // Edges: vertices differing in exactly one bit.
    for (const u of verts) {
      for (const v of verts) {
        const diff = u.reduce((n, x, i) => n + (x !== v[i] ? 1 : 0), 0);
        if (diff === 1 && u.join("") < v.join("")) {
          const p = P(...u);
          const q = P(...v);
          const back = u[2] === 0 && v[2] === 0 ? false : u[2] === 1 && v[2] === 1;
          svg.append(s("line", { x1: p.x, y1: p.y, x2: q.x, y2: q.y, stroke: "var(--rule-strong)", "stroke-width": 1.2, "stroke-dasharray": back ? "3 3" : "" }));
        }
      }
    }
    // Axis labels on the three edges leaving 000.
    const mid = (a: [number, number, number], b: [number, number, number]) => {
      const p = P(...a);
      const q = P(...b);
      return { x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 };
    };
    const fs = Math.max(10, 11.5 * k);
    const m1 = mid([0, 0, 0], [1, 0, 0]);
    const m2 = mid([0, 0, 0], [0, 1, 0]);
    const m3 = mid([0, 0, 0], [0, 0, 1]);
    svg.append(
      s("text", { x: m1.x + 20 * k, y: m1.y - 8 * k, "text-anchor": "middle", "font-size": fs, fill: "var(--ink)" }, ["A1 queue position →"]),
      s("text", { x: m2.x - 10 * k, y: m2.y, "text-anchor": "end", "font-size": fs, fill: "var(--ink)" }, ["A2 adverse"]),
      s("text", { x: m2.x - 10 * k, y: m2.y + fs + 2, "text-anchor": "end", "font-size": fs, fill: "var(--ink)" }, ["selection ↑"]),
      s("text", { x: m3.x - 8 * k, y: m3.y - 6 * k, "text-anchor": "end", "font-size": fs, fill: "var(--ink)" }, ["A3 competition ↗"]),
    );
    for (const v of verts) {
      const p = P(...v);
      const id = v.join("");
      const special = id === "000" || id === "111";
      svg.append(
        s("circle", { cx: p.x, cy: p.y, r: special ? 6 : 4.5, fill: id === "000" ? "var(--accent)" : id === "111" ? "var(--ink)" : "var(--surface)", stroke: special ? "var(--surface)" : "var(--ink-2)", "stroke-width": 1.5 }),
        s("text", { x: p.x + 9 * k, y: p.y - 7 * k, "font-size": fs - 1, class: "mono-t", fill: "var(--ink-2)" }, [id]),
      );
    }
    const a = P(0, 0, 0);
    const b = P(1, 1, 1);
    svg.append(
      s("text", { x: a.x - 8 * k, y: a.y + 28 * k, "text-anchor": "start", "font-size": fs, fill: "var(--accent)" }, ["000: the paper's world, reduces to M1"]),
      s("text", { x: b.x, y: b.y - 18 * k, "text-anchor": "end", "font-size": fs, fill: "var(--ink)" }, ["111: all three switched on"]),
    );
    host.replaceChildren(svg);
  });
}

/** Planned per-day split, with the episode counts the pipeline's rounding produces. */
export function mountSplit(host: HTMLElement): void {
  const episodes = 78; // 09:30-16:00 in 300 s episodes
  const cal = Math.round(episodes * 0.4);
  const fit = Math.round(episodes * 0.3);
  const hold = episodes - cal - fit;
  const clock = (n: number) => {
    const m = 9 * 60 + 30 + n * 5;
    return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  };
  responsive(host, (w) => {
    const width = Math.min(w, 560);
    const narrow = width < 420;
    const H = narrow ? 150 : 130;
    const x0 = 2;
    const x1 = width - 2;
    const X = (n: number) => x0 + (n / episodes) * (x1 - x0);
    const svg = svgRoot(width, H, `Each day split into ${cal} calibration, ${fit} policy-fit and ${hold} holdout episodes`);
    const segs: [number, number, string, string, string][] = [
      [0, cal, "Calibration", `${cal} episodes`, "var(--rule)"],
      [cal, cal + fit, "Policy fit", `${fit} episodes`, "var(--accent-soft)"],
      [cal + fit, episodes, "Holdout, locked", `${hold} episodes`, "var(--ask-soft)"],
    ];
    const y = 34;
    for (const [a, b, name, count, fill] of segs) {
      svg.append(
        s("rect", { x: X(a) + 1, y, width: X(b) - X(a) - 2, height: 30, fill, stroke: name.startsWith("Holdout") ? "var(--ask)" : "none", "stroke-dasharray": "4 3" }),
        s("text", { x: X(a) + 6, y: y - 16, "font-size": narrow ? 10.5 : 12, "font-weight": 600, fill: "var(--ink)" }, [name]),
        s("text", { x: X(a) + 6, y: y - 3, "font-size": narrow ? 10 : 11, fill: "var(--muted)" }, [count]),
      );
    }
    for (const n of [0, cal, cal + fit, episodes]) {
      svg.append(
        s("line", { x1: X(n), x2: X(n), y1: y + 30, y2: y + 38, stroke: "var(--rule-strong)" }),
        s("text", { x: X(n), y: y + 52, "text-anchor": n === 0 ? "start" : n === episodes ? "end" : "middle", "font-size": 11, class: "mono-t", fill: "var(--muted)" }, [clock(n)]),
      );
    }
    svg.append(
      s("text", { x: 0, y: H - 10, "font-size": 11, fill: "var(--muted)" }, [
        narrow ? "Fit on the past, test on the next episode." : "Walk-forward inside the policy-fit block: fit on earlier episodes, test on the next one.",
      ]),
    );
    host.replaceChildren(svg);
  });
}
