// Inlines the built CSS and JS into one self-contained HTML file.
// Usage: npm run build && npm run single -- <output.html outside dist/> [--fragment]
// --fragment drops the document wrapper (for hosts that add their own).
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const [out, flag] = process.argv.slice(2);
if (!out || out.startsWith(join(root, "dist")) || out.startsWith("dist")) {
  throw new Error("give an output path outside dist/, so the file is never deployed");
}
let html = readFileSync(join(root, "dist/index.html"), "utf8");
html = html.replace(/<link rel="stylesheet"[^>]*href="\/?(assets\/[^"]+\.css)"[^>]*>/, (_, p) => {
  // Embed woff2 fonts; drop the woff fallbacks (every current browser uses woff2).
  const css = readFileSync(join(root, "dist", p), "utf8")
    .replace(/,\s*url\(\/?assets\/[^)]+\.woff\) format\("woff"\)/g, "")
    .replace(/url\(\/?(assets\/[^)]+\.woff2)\)/g, (_, f) =>
      `url(data:font/woff2;base64,${readFileSync(join(root, "dist", f)).toString("base64")})`,
    );
  return `<style>${css}</style>`;
});
html = html.replace(/<link rel="preload" as="font"[^>]*>/g, "");
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
