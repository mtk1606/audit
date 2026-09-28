// Inlines the built CSS and JS into one self-contained HTML file.
// Usage: npm run build && npm run single -- <output.html> [--fragment]
// --fragment drops the document wrapper (for hosts that add their own).
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const [out = join(root, "dist/single.html"), flag] = process.argv.slice(2);
let html = readFileSync(join(root, "dist/index.html"), "utf8");
html = html.replace(/<link rel="stylesheet"[^>]*href="\/?(assets\/[^"]+\.css)"[^>]*>/, (_, p) =>
  `<style>${readFileSync(join(root, "dist", p), "utf8")}</style>`,
);
html = html.replace(/<script type="module" crossorigin src="\/?(assets\/[^"]+\.js)"><\/script>/, (_, p) =>
  `<script type="module">${readFileSync(join(root, "dist", p), "utf8").replace(/<\/script/g, "<\\/script")}</script>`,
);
if (html.includes('src="/assets') || html.includes('href="/assets')) throw new Error("asset left un-inlined");
if (flag === "--fragment") {
  const head = html.match(/<head>([\s\S]*)<\/head>/)?.[1] ?? "";
  const body = html.match(/<body>([\s\S]*)<\/body>/)?.[1] ?? "";
  html = head.replace(/<meta charset[^>]*>|<meta name="viewport"[^>]*>/g, "") + body;
}
writeFileSync(out, html);
console.log(`single-file page written: ${out} (${Math.round(html.length / 1024)} KB)`);
