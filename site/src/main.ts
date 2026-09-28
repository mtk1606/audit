import "./styles.css";
import evidence from "./data/evidence.json";
import { claims } from "./claims.mjs";
import { LINKS, reportUrl } from "./config";
import { mountQueue } from "./figures/queue";
import { mountQuotes } from "./figures/quotes";
import { mountZChart, type ZRun } from "./figures/zchart";
import { mountGrid, mountSplit } from "./figures/diagrams";

// Evidence-backed text. The static HTML already holds the same values (checked at
// build time by scripts/check-claims.mjs); rendering them again keeps one source.
const values = claims(evidence);
for (const node of document.querySelectorAll<HTMLElement>("[data-ev]")) {
  const key = node.dataset.ev ?? "";
  const value = values[key];
  if (value === undefined) {
    console.warn(`Unknown evidence key: ${key}`);
    continue;
  }
  node.textContent = value;
}

for (const a of document.querySelectorAll<HTMLAnchorElement>("a[data-link]")) {
  const key = a.dataset.link as keyof typeof LINKS;
  if (LINKS[key]) a.href = LINKS[key];
}
for (const a of document.querySelectorAll<HTMLAnchorElement>("a[data-report]")) {
  a.href = reportUrl(a.dataset.report ?? "");
}
for (const a of document.querySelectorAll<HTMLAnchorElement>('a[href^="http"]')) {
  a.rel = "noopener";
}

// Each figure fails on its own, leaving a note instead of a broken page.
function mount(id: string, fn: (el: HTMLElement) => void, fallback: string): void {
  const el = document.getElementById(id);
  if (!el) return;
  try {
    fn(el);
  } catch (err) {
    console.error(`Figure ${id} failed`, err);
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = fallback;
    el.append(note);
  }
}

const params = evidence.m1.params;
mount("fig-queue", (el) => mountQueue(el), "The interactive queue could not load. The rule it shows: executions at a price fill the orders ahead of you first.");
mount(
  "fig-quotes",
  (el) => mountQuotes(el, { s0: params.s0, sigma: params.sigma, k: params.k, A: params.A, dt: params.dt }),
  "The quote explorer could not load. The equations are in the technical detail below.",
);
mount(
  "fig-z",
  (el) => mountZChart(el, evidence.m1.runs as ZRun[], evidence.m1.threshold),
  "The chart could not load. The same values are in sensitivity.json, linked below.",
);
mount("grid-svg", (el) => mountGrid(el), "Diagram unavailable.");
mount("split-svg", (el) => mountSplit(el), "Diagram unavailable.");

// Scroll containers that actually overflow must be reachable by keyboard.
function markScrollRegions(): void {
  for (const el of document.querySelectorAll<HTMLElement>(".table-wrap, .cmd pre, .eq")) {
    if (el.scrollWidth > el.clientWidth + 1) {
      el.tabIndex = 0;
      el.setAttribute("role", "region");
      if (!el.hasAttribute("aria-label")) el.setAttribute("aria-label", "Scrollable content");
    } else if (el.getAttribute("aria-label") === "Scrollable content") {
      el.removeAttribute("tabindex");
      el.removeAttribute("role");
      el.removeAttribute("aria-label");
    }
  }
}
markScrollRegions();
window.addEventListener("resize", () => requestAnimationFrame(markScrollRegions));
document.querySelectorAll("details").forEach((d) => d.addEventListener("toggle", markScrollRegions));
