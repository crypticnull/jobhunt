import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { projectSchema, pipelineSchema, proofSchema } from "./schemas.mjs";

// Records live in /data, outside the site, because letters and the site read
// the same files. The slug directory is the id.
const bySlugDir = ({ entry }) => entry.split("/")[0];

const projects = defineCollection({
  loader: glob({ pattern: "*/index.md", base: "../data/projects", generateId: bySlugDir }),
  schema: projectSchema,
});

const pipelines = defineCollection({
  loader: glob({ pattern: "*/index.md", base: "../data/pipelines", generateId: bySlugDir }),
  schema: pipelineSchema,
});

const proof = defineCollection({
  loader: glob({ pattern: "*.md", base: "../data/proof" }),
  schema: proofSchema,
});

export const collections = { projects, pipelines, proof };
