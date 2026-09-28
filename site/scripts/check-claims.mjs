// Build gate for public claims. Fails when:
//  1. a static evidence value in index.html differs from the value computed
//     from evidence.json, or uses an unknown key;
//  2. an evidence value sits in a block (p, li, dd, td, figcaption, small)
//     without a numbered source mark (<a class="src" href="#sN">);
//  3. a source mark points at a source that does not exist.
// The source list itself (<ol class="sources">) is exempt from rule 2.
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { claims } from "../src/claims.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const ev = JSON.parse(readFileSync(join(root, "src/data/evidence.json"), "utf8"));
const html = readFileSync(join(root, "index.html"), "utf8");
const values = claims(ev);
const errors = [];

const sourcesStart = html.indexOf('<ol class="sources">');
const sourcesEnd = html.indexOf("</ol>", sourcesStart);
const BLOCKS = ["small", "li", "dd", "td", "figcaption", "p"];

function enclosingBlock(at) {
  let best = null;
  for (const tag of BLOCKS) {
    const open = html.lastIndexOf(`<${tag}`, at);
    if (open < 0) continue;
    const close = html.indexOf(`</${tag}>`, at);
    const reopened = html.indexOf(`<${tag}`, open + 1);
    if (close < 0 || (reopened > open && reopened < at)) continue;
    if (!best || open > best.open) best = { open, close: close + tag.length + 3, tag };
  }
  return best;
}

const found = [...html.matchAll(/<span data-ev="([^"]+)">([^<]*)<\/span>/g)];
for (const m of found) {
  const [, key, text] = m;
  if (!(key in values)) errors.push(`unknown key ${key}`);
  else if (values[key] !== text) errors.push(`${key}: page says "${text}", evidence says "${values[key]}"`);
  const at = m.index ?? 0;
  if (at > sourcesStart && at < sourcesEnd) continue;
  const block = enclosingBlock(at);
  if (!block || !html.slice(block.open, block.close).includes('class="src"')) {
    errors.push(`${key}: no source mark in its <${block?.tag ?? "?"}> block`);
  }
}
const ids = new Set([...html.matchAll(/<li id="(s\d+)"/g)].map((m) => m[1]));
for (const m of html.matchAll(/class="src" href="#(s\d+)"/g)) {
  if (!ids.has(m[1])) errors.push(`source mark #${m[1]} has no entry in the source list`);
}
if (errors.length) {
  console.error(`Claim check failed:\n  ${errors.join("\n  ")}`);
  process.exit(1);
}
console.log(
  `Claim check passed: ${found.length} evidence values match the evidence and carry a source; ${ids.size} sources listed.`,
);
