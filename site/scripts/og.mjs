// Renders public/og.png (1200x630) from the real M1 evidence.
// Usage: CHROMIUM_PATH=/path/to/chrome npm run og
import { chromium } from "playwright-core";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const ev = JSON.parse(readFileSync(join(root, "src/data/evidence.json"), "utf8"));
const run = ev.m1.runs.find((r) => r.rule === "saturate" && r.dt === 0.005);
const zs = run.tests.filter((t) => t.status === "tested").map((t) => t.z);
const th = ev.m1.threshold;
const W = 460, H = 300, x = (z) => 20 + ((z + 4) / 8) * (W - 40);
const dots = zs.map((z, i) => `<circle cx="${x(z)}" cy="${30 + i * 9}" r="3.6" fill="#2b59c3"/>`).join("");
const svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
<rect x="${x(-th)}" y="18" width="${x(th) - x(-th)}" height="${zs.length * 9 + 16}" fill="rgba(43,89,195,0.09)"/>
<line x1="${x(0)}" x2="${x(0)}" y1="18" y2="${zs.length * 9 + 34}" stroke="#b9bec7"/>${dots}
<text x="${x(-th)}" y="12" font-size="13" text-anchor="middle" fill="#2b59c3" font-family="IBM Plex Mono, monospace">−${th.toFixed(2)}</text>
<text x="${x(th)}" y="12" font-size="13" text-anchor="middle" fill="#2b59c3" font-family="IBM Plex Mono, monospace">+${th.toFixed(2)}</text></svg>`;
const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet">
<style>body{margin:0;width:1200px;height:630px;background:#f6f7f8;font-family:"IBM Plex Sans",system-ui,sans-serif;color:#15181d}
.w{display:grid;grid-template-columns:1fr 480px;gap:40px;padding:64px 64px 0}
.k{font-family:"IBM Plex Mono",monospace;font-size:17px;letter-spacing:.08em;text-transform:uppercase;color:#6c7480}
h1{font-family:"Source Serif 4",Georgia,serif;font-weight:600;font-size:54px;line-height:1.08;margin:22px 0 26px;letter-spacing:-.01em}
p{font-size:21px;line-height:1.45;color:#454c57;margin:0}
.c{font-size:16px;color:#6c7480;margin-top:10px}
.f{position:absolute;left:64px;right:64px;bottom:44px;display:flex;justify-content:space-between;border-top:1px solid #dcdfe4;padding-top:18px;font-size:20px}
.f b{font-weight:600}</style></head><body><div class="w"><div>
<div class="k">Market microstructure research</div>
<h1>What happens when a famous market-making model meets a real order queue?</h1>
<p>An audit of Avellaneda-Stoikov (2008). The replication is settled; real-market attribution is next.</p></div>
<div style="padding-top:28px">${svg}<div class="c">All ${zs.length} published values inside the ±${th.toFixed(2)} band under capped fills. Exact computation.</div></div></div>
<div class="f"><b>Mohamed El Khoudimi</b><span>Replication · simulator · attribution</span></div></body></html>`;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.setContent(html, { waitUntil: "networkidle" }).catch(() => page.setContent(html));
await page.screenshot({ path: join(root, "public/og.png") });
await browser.close();
console.log("public/og.png written");
