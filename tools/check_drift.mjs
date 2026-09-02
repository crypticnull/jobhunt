#!/usr/bin/env node
// Asserts each site collection's zod schema matches its JSON Schema in
// data/schema: same top-level fields, same required set. Run from the repo
// root after `npm install` in /site. Exit 1 on drift.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { z, projectSchema, pipelineSchema, proofSchema, writingSchema, chapterSchema } from "../site/src/schemas.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const image = () => z.string();

const pairs = [
  ["project", projectSchema({ image })],
  ["pipeline", pipelineSchema({ image })],
  ["proof", proofSchema({ image })],
  ["writing", writingSchema({ image })],
  ["chapter", chapterSchema()],
];

let drift = 0;
for (const [name, zodSchema] of pairs) {
  const json = JSON.parse(readFileSync(join(root, "data", "schema", `${name}.schema.json`), "utf8"));
  const jsonFields = new Set(Object.keys(json.properties));
  const jsonRequired = new Set(json.required);
  const zodFields = new Set(Object.keys(zodSchema.shape));
  const zodRequired = new Set(
    Object.entries(zodSchema.shape)
      .filter(([, s]) => !s.isOptional())
      .map(([k]) => k),
  );

  const report = (label, a, b) => {
    for (const k of a) if (!b.has(k)) { console.error(`${name}: ${label} ${k}`); drift++; }
  };
  report("field only in JSON Schema:", jsonFields, zodFields);
  report("field only in zod:", zodFields, jsonFields);
  report("required only in JSON Schema:", jsonRequired, zodRequired);
  report("required only in zod:", zodRequired, jsonRequired);
}

if (drift) {
  console.error(`check_drift: ${drift} difference(s)`);
  process.exit(1);
}
console.log("check_drift: schemas in step");
