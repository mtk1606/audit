// Replication result: z-score of every printed value against the exact
// population law of each candidate rule. Data: docs/evidence/m1-sensitivity.
import { s, svgRoot, linear, responsive, fmt } from "./svg";

export interface ZTest {
  table: number;
  gamma: number;
  strategy: string;
  metric: string;
  label?: string;
  paper?: number;
  population?: number;
  z?: number;
  status: string;
}

export interface ZRun {
  rule: string;
  dt: number;
  tests_run: number;
  failures: number;
  max_abs_z: number;
  tests: ZTest[];
}

const LIMIT = 6;
const METRIC_ORDER = ["profit_mean", "profit_std", "final_q_mean", "final_q_std", "variance_ratio"];
const STRATEGY_ORDER = ["inventory", "symmetric", "both"];

function ordered(tests: ZTest[]): ZTest[] {
  const key = (t: ZTest) =>
    t.table * 100 + STRATEGY_ORDER.indexOf(t.strategy) * 10 + METRIC_ORDER.indexOf(t.metric);
  return [...tests].sort((a, b) => key(a) - key(b));
}
const RULE_NAME: Record<string, string> = { saturate: "Capped", poisson: "Poisson", strict: "Strict" };

function rowLabel(t: ZTest): string {
  const who = t.strategy === "inventory" ? "Inventory" : t.strategy === "symmetric" ? "Symmetric" : "";
  return t.metric === "variance_ratio" ? "Variance ratio" : `${who} · ${t.label ?? t.metric}`;
}

export function takeaway(run: ZRun, threshold: number): string {
  const inside = run.tests_run - run.failures;
  const name = `${RULE_NAME[run.rule] ?? run.rule} fills at dt ${run.dt}`;
  if (run.failures === 0) return `${name}: all ${run.tests_run} values fall inside the band.`;
  return `${name}: ${run.failures} of ${run.tests_run} values fall outside ±${fmt(threshold)}, the worst at ${fmt(run.max_abs_z, 1)} standard errors. ${inside} inside.`;
}

export function mountZChart(root: HTMLElement, runs: ZRun[], threshold: number): void {
  const host = root.querySelector<HTMLElement>("#z-svg");
  const select = root.querySelector<HTMLElement>("#z-select");
  const note = root.querySelector<HTMLElement>("#z-takeaway");
  const tableHost = root.querySelector<HTMLElement>("#z-table");
  if (!host || !select || !note || !tableHost) throw new Error("z chart markup missing");
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  tip.setAttribute("role", "status");
  host.after(tip);
  host.parentElement?.classList.add("chart-host");

  let current = runs.find((r) => r.rule === "saturate" && r.dt === 0.005);
  if (!current) throw new Error("capped run missing from evidence");
  let width = 720;

  const draw = () => {
    const run = current as ZRun;
    const tests = ordered(run.tests.filter((t) => t.status === "tested" && t.z !== undefined));
    const narrow = width < 560;
    const labelW = narrow ? Math.min(150, width * 0.42) : 230;
    const rowH = narrow ? 17 : 19;
    const groupGap = 26;
    const top = 30;
    const tables = [...new Set(tests.map((t) => t.table))];
    const H = top + tables.length * groupGap + tests.length * rowH + 34;
    const x = linear(-LIMIT, LIMIT, labelW + 14, width - 40);
    const svg = svgRoot(width, H, `Z-scores for ${tests.length} published values under ${RULE_NAME[run.rule]} fills at dt ${run.dt}`);

    // Band, zero and grid.
    svg.append(s("rect", { x: x(-threshold), y: top - 8, width: x(threshold) - x(-threshold), height: H - top - 26, fill: "var(--band)" }));
    for (const v of [-6, -3, 0, 3, 6]) {
      svg.append(
        s("line", { x1: x(v), x2: x(v), y1: top - 8, y2: H - 34, stroke: v === 0 ? "var(--rule-strong)" : "var(--rule)", "stroke-dasharray": v === 0 ? "" : "2 3" }),
        s("text", { x: x(v), y: H - 18, "text-anchor": "middle", "font-size": 11, class: "mono-t", fill: "var(--muted)" }, [v > 0 ? `+${v}` : String(v)]),
      );
    }
    svg.append(
      s("text", { x: x(threshold), y: top - 14, "text-anchor": "middle", "font-size": 10.5, fill: "var(--accent)" }, [`+${fmt(threshold)}`]),
      s("text", { x: x(-threshold), y: top - 14, "text-anchor": "middle", "font-size": 10.5, fill: "var(--accent)" }, [`−${fmt(threshold)}`]),
      s("text", { x: (x(-LIMIT) + x(LIMIT)) / 2, y: H - 2, "text-anchor": "middle", "font-size": 11, fill: "var(--muted)" }, [
        narrow ? "Standard errors from exact expectation" : "Standard errors from the exact expectation (paper's 1,000-path estimate)",
      ]),
    );

    let y = top;
    for (const table of tables) {
      const group = tests.filter((t) => t.table === table);
      const g0 = group[0];
      y += groupGap - 8;
      svg.append(
        s("text", { x: 0, y: y - 4, "font-size": 12, "font-weight": 600, fill: "var(--ink)" }, [
          `Table ${table}  ·  γ = ${g0?.gamma ?? ""}`,
        ]),
      );
      y += 8;
      for (const t of group) {
        const z = t.z as number;
        const cy = y + rowH / 2;
        const outside = Math.abs(z) > threshold;
        const clipped = Math.abs(z) > LIMIT;
        const cx = x(Math.max(-LIMIT, Math.min(LIMIT, z)));
        const label = rowLabel(t);
        svg.append(
          s("text", { x: 0, y: cy + 4, "font-size": narrow ? 10.5 : 11.5, fill: "var(--ink-2)" }, [
            narrow ? label.replace("Final inventory", "Inventory").replace("Inventory · ", "Inv. · ").replace("Symmetric · ", "Sym. · ") : label,
          ]),
          s("line", { x1: labelW + 14, x2: width - 40, y1: cy, y2: cy, stroke: "var(--rule)", "stroke-width": 0.5 }),
        );
        const hit = s("g", { tabindex: 0, role: "button", "aria-label": `${label}, table ${table}: paper ${t.paper}, exact ${fmt(t.population ?? 0, 3)}, z ${fmt(z)}` });
        hit.append(s("rect", { x: labelW + 14, y, width: width - 54 - labelW, height: rowH, fill: "transparent" }));
        if (outside) {
          hit.append(
            s("path", { d: `M${cx},${cy - 6} L${cx + 6},${cy} L${cx},${cy + 6} L${cx - 6},${cy} Z`, fill: "var(--surface)", stroke: "var(--ask)", "stroke-width": 2 }),
          );
        } else {
          hit.append(s("circle", { cx, cy, r: 4.5, fill: "var(--accent)", stroke: "var(--surface)", "stroke-width": 1.5 }));
        }
        if (clipped) {
          const dir = z > 0 ? 1 : -1;
          svg.append(
            s("text", { x: cx + dir * 10, y: cy + 4, "text-anchor": dir > 0 ? "start" : "end", "font-size": 10.5, class: "mono-t", fill: "var(--ask)" }, [
              `${z > 0 ? "+" : "−"}${fmt(Math.abs(z), 1)} →`,
            ]),
          );
        }
        const show = () => {
          tip.hidden = false;
          tip.innerHTML = "";
          const lines = [
            `<strong>${label}</strong>, Table ${table}`,
            `Paper printed: <span class="mono">${t.paper}</span>`,
            `Exact expectation: <span class="mono">${fmt(t.population ?? 0, 3)}</span>`,
            `Distance: <span class="mono">${z > 0 ? "+" : "−"}${fmt(Math.abs(z))}</span> standard errors`,
          ];
          tip.innerHTML = lines.join("<br>");
          const fig = root.getBoundingClientRect();
          const box = host.getBoundingClientRect();
          const scale = box.width / width;
          const left = box.left - fig.left + cx * scale + 12;
          tip.style.left = `${Math.max(0, Math.min(left, fig.width - 280))}px`;
          tip.style.top = `${box.top - fig.top + (cy + 10) * scale}px`;
        };
        const hide = () => {
          tip.hidden = true;
        };
        hit.addEventListener("pointerenter", show);
        hit.addEventListener("focus", show);
        hit.addEventListener("pointerleave", hide);
        hit.addEventListener("blur", hide);
        svg.append(hit);
        y += rowH;
      }
    }
    host.replaceChildren(svg);
    note.textContent = takeaway(run, threshold);
    renderTable(tableHost, run, threshold);
  };

  for (const btn of select.querySelectorAll<HTMLButtonElement>("button[data-rule]")) {
    btn.addEventListener("click", () => {
      const found = runs.find((r) => r.rule === btn.dataset.rule && r.dt === Number(btn.dataset.dt));
      if (!found) return;
      current = found;
      for (const b of select.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === btn));
      tip.hidden = true;
      draw();
    });
  }
  responsive(host, (w) => {
    width = Math.min(w, 940);
    draw();
  });
}

function renderTable(host: HTMLElement, run: ZRun, threshold: number): void {
  const rows = ordered(run.tests.filter((t) => t.status === "tested"))
    .map(
      (t) =>
        `<tr><td>Table ${t.table}</td><td>${rowLabel(t)}</td><td class="r mono">${t.paper}</td><td class="r mono">${fmt(t.population ?? 0, 3)}</td><td class="r mono">${fmt(t.z ?? 0)}</td><td>${Math.abs(t.z ?? 0) > threshold ? "Outside" : "Inside"}</td></tr>`,
    )
    .join("");
  host.innerHTML = `<table><caption class="visually-hidden">Replication z-scores</caption><thead><tr><th scope="col">Table</th><th scope="col">Value</th><th scope="col" class="r">Paper</th><th scope="col" class="r">Exact</th><th scope="col" class="r">z</th><th scope="col">Band</th></tr></thead><tbody>${rows}</tbody></table>`;
}
