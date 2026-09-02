import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { projectSchema, pipelineSchema, proofSchema, writingSchema, chapterSchema } from "./schemas.mjs";

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

// data/projects/<slug>/chapters/NN-kind.md. The id keeps the slug and the file
// stem, so a study can select its own chapters without a second lookup.
const chapters = defineCollection({
  loader: glob({ pattern: "*/chapters/*.md", base: "../data/projects", generateId: ({ entry }) => entry.replace(/\.md$/, "") }),
  schema: chapterSchema,
});

const proof = defineCollection({
  loader: glob({ pattern: "*.md", base: "../data/proof" }),
  schema: proofSchema,
});

const writing = defineCollection({
  loader: glob({ pattern: "*.md", base: "../data/writing" }),
  schema: writingSchema,
});

export const collections = { projects, pipelines, chapters, proof, writing };
