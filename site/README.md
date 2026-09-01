# site

The portfolio site: Astro 7, static output (ADR-0005), deployed on
Cloudflare Workers static assets (ADR-0006). The only npm tree in the repo
lives here.

## Content

The site owns no content. It reads `/data` through three collections
declared in `src/content.config.mjs`, with zod schemas in `src/schemas.mjs`
that mirror `data/schema/*.schema.json`. `tools/check_drift.mjs` fails CI
when the two diverge.

| Collection | Source | Page |
| --- | --- | --- |
| projects | `data/projects/<slug>/index.md` | `/work/<slug>` |
| pipelines | `data/pipelines/<slug>/index.md` | `/builds/<slug>` |
| proof | `data/proof/<id>.md` | cards in What I build |

Adding a project is a directory drop: the record plus its `assets/`, no code.
Stills go through Astro's image pipeline; the hero is required and is the
poster for any video, so the box is reserved before bytes arrive.

## Running it

```
npm install
npm run dev        # local preview
npm run build      # static output in dist/
npm run lighthouse # the CI budgets: CLS 0, performance 90+, accessibility 95+
```

Site-wide copy and links live in `src/site.config.mjs`. The production URL
is passed in as `SITE_URL` by the deploy workflow.
