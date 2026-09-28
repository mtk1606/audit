const NS = "http://www.w3.org/2000/svg";

type Attrs = Record<string, string | number | undefined>;

export function s<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Attrs = {},
  children: (SVGElement | string)[] = [],
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== undefined) node.setAttribute(k, String(v));
  }
  for (const c of children) node.append(typeof c === "string" ? document.createTextNode(c) : c);
  return node;
}

export function svgRoot(width: number, height: number, label: string): SVGSVGElement {
  return s("svg", {
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    role: "img",
    "aria-label": label,
    preserveAspectRatio: "xMinYMin meet",
  });
}

export function linear(d0: number, d1: number, r0: number, r1: number): (x: number) => number {
  const k = (r1 - r0) / (d1 - d0);
  return (x) => r0 + (x - d0) * k;
}

/** Nice ticks covering [lo, hi]. */
export function ticks(lo: number, hi: number, count = 6): number[] {
  const span = hi - lo;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((x) => span / x <= count) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

/** Re-render on container resize, debounced to animation frames. */
export function responsive(host: HTMLElement, draw: (width: number) => void): void {
  let last = -1;
  let frame = 0;
  const run = () => {
    const w = Math.round(host.clientWidth);
    if (w > 0 && w !== last) {
      last = w;
      draw(w);
    }
  };
  run();
  if ("ResizeObserver" in window) {
    new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(run);
    }).observe(host);
  }
}

export function fmt(x: number, digits = 2): string {
  return x.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
