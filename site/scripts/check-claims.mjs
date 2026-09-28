// Fails the build if any static evidence value in index.html differs from the
// value computed from evidence.json, or if a data-ev key is unknown.
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { claims } from "../src/claims.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const ev = JSON.parse(readFileSync(join(root, "src/data/evidence.json"), "utf8"));
const html = readFileSync(join(root, "index.html"), "utf8");
const values = claims(ev);
const found = [...html.matchAll(/<span data-ev="([^"]+)">([^<]*)<\/span>/g)];
const errors = [];
for (const [, key, text] of found) {
  if (!(key in values)) errors.push(`unknown key ${key}`);
  else if (values[key] !== text) errors.push(`${key}: page says "${text}", evidence says "${values[key]}"`);
}
if (errors.length) {
  console.error(`Claim check failed:\n  ${errors.join("\n  ")}`);
  process.exit(1);
}
console.log(`Claim check passed: ${found.length} evidence values match ${Object.keys(values).length} computed claims.`);
