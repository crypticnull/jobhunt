// Zod mirrors of data/schema/*.schema.json. tools/check_drift.mjs asserts the
// two stay in step, so a field added on either side without the other fails CI.
import { z } from "astro/zod";

// Re-exported so tools/check_drift.mjs, which lives outside /site, gets the
// same zod instance without its own dependency.
export { z };

const video = z.object({
  provider: z.enum(["none", "r2", "bunny", "youtube", "vimeo", "self"]),
  mp4: z.array(z.string()).default([]),
  hls: z.string().nullable().optional(),
  poster: z.string().nullable().optional(),
  width: z.number().int(),
  height: z.number().int(),
  duration: z.number().nullable().optional(),
});

// image is Astro's image() helper at build time and a plain string schema in
// the drift check, which only compares shapes.
const still = (image) =>
  z.object({
    src: image(),
    width: z.number().int(),
    height: z.number().int(),
    alt: z.string(),
  });

export const projectSchema = ({ image }) =>
  z.object({
    slug: z.string().regex(/^[a-z0-9-]+$/),
    title: z.string(),
    franchise: z.string().nullable().optional(),
    year: z.number().int(),
    client: z.string(),
    role: z.string(),
    disciplines: z.array(
      z.enum(["3d", "motion", "brand-system", "key-art", "generative", "art-direction", "systems-design", "compositing"]),
    ),
    tools: z.array(z.string()),
    turnaround: z.string().nullable().optional(),
    summary: z.string(),
    featured: z.boolean(),
    archive: z.boolean().default(false),
    order: z.number().int().default(100),
    hero: still(image),
    video: video.optional(),
    stills: z.array(still(image)).default([]),
    process: z
      .array(
        z.object({
          kind: z.enum(["storyboard", "styleframe", "wip", "breakdown"]),
          src: image(),
          width: z.number().int(),
          height: z.number().int(),
          alt: z.string(),
          caption: z.string().optional(),
        }),
      )
      .default([]),
  });

export const pipelineSchema = ({ image }) =>
  z.object({
    slug: z.string().regex(/^[a-z0-9-]+$/),
    title: z.string(),
    kind: z.enum(["comfyui-graph", "node-pack", "panel-backend", "tool"]),
    status: z.enum(["production", "wip", "archived"]),
    nodes: z.number().int().nullable().optional(),
    models: z.array(z.string()),
    hardware: z.string(),
    graph: still(image).nullable().optional(),
    workflow_json: z.string().nullable().optional(),
    demo: video.nullable().optional(),
    repo: z.string().nullable().optional(),
    linked_proof: z.string(),
    writeup: z.string().nullable().optional(),
    summary: z.string(),
    order: z.number().int().default(100),
  });

// An inventory for a build whose scale is itself the proof. The counts live in
// data rather than in a sentence, because a number written into prose goes
// stale silently and a number computed from a record cannot. Categories carry
// no tool names, which is what makes it publishable before a product ships.
const manifest = z.object({
  label: z.string(),
  version: z.string().nullable().optional(),
  updated: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().optional(),
  categories: z
    .array(z.object({ name: z.string(), count: z.number().int().min(0) }))
    .default([]),
});

export const proofSchema = () =>
  z.object({
    id: z.string().regex(/^[a-z0-9-]+$/),
    title: z.string(),
    leads_for: z.array(z.enum(["ai-video", "studio-ai", "product-inhouse", "brand-inhouse"])),
    linked_projects: z.array(z.string()).default([]),
    linked_pipelines: z.array(z.string()).default([]),
    repo: z.string().nullable().optional(),
    summary: z.string(),
    manifest: manifest.nullable().optional(),
    order: z.number().int().default(100),
  });

export const writingSchema = () =>
  z.object({
    slug: z.string().regex(/^[a-z0-9-]+$/),
    title: z.string(),
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    summary: z.string(),
    draft: z.boolean().default(false),
    linked_pipelines: z.array(z.string()).default([]),
  });
