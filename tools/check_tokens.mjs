#!/usr/bin/env node
// The teeth behind ADR-0012. Three checks, exit 1 on any failure:
//   1. site/src/styles/tokens.css is exactly what tools/tokens.mjs renders
//      from data/design/tokens.json, so the record and the CSS cannot drift.
//   2. Every text pair in the record measures 4.5 to 1 or better in both
//      themes, so a palette tweak that breaks contrast fails here, not on a
//      stranger's screen.
//   3. No .astro or .mjs file under site/src writes a hex colour, a
//      millisecond duration or a cubic-bezier by hand. A component names a
//      token, never a number.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { load, ratios, render, root, OUTPUT } from "./tokens.mjs";

let failures = 0;
const fail = (msg) => { console.error(`check_tokens: ${msg}`); failures++; };

const record = load();
const rendered = render(record);
let committed = "";
try { committed = readFileSync(OUTPUT, "utf8"); } catch { fail(`${relative(root, OUTPUT)} is missing, run node tools/tokens.mjs`); }
if (committed && committed !== rendered) fail(`${relative(root, OUTPUT)} is stale, run node tools/tokens.mjs`);

for (const r of ratios(record)) {
  if (r.text && r.ratio < 4.5) fail(`${r.fg} on ${r.bg} in ${r.theme} measures ${r.ratio}, under 4.5`);
  if (!r.text && r.ratio >= 4.5) console.warn(`check_tokens: ${r.fg} on ${r.bg} is marked decorative but measures ${r.ratio}`);
}

const walk = (dir) => readdirSync(dir).flatMap((f) => {
  const p = join(dir, f);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
const literal = [
  [/#[0-9a-f]{3}(?:[0-9a-f]{3})?\b/i, "hex colour"],
  [/(?:transition|animation)[^;{}]*?\b\d+m?s\b/, "duration literal in a transition or animation"],
  [/cubic-bezier\(/, "easing curve"],
];
for (const file of walk(join(root, "site", "src")).filter((f) => /\.(astro|mjs)$/.test(f))) {
  const text = readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")   // block comments
    .replace(/^\s*\/\/.*$/gm, "");        // line comments
  for (const [re, what] of literal) {
    const m = text.match(re);
    if (m) fail(`${relative(root, file)}: ${what} written by hand: ${m[0].trim()}`);
  }
}

if (failures) process.exit(1);
console.log(`check_tokens: record, CSS and contrast in step, ${ratios(record).length} pairs measured`);
