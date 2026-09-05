# Project brief — portfolio site, job scraper, cover letter generator

For a fresh Claude Code project. Most of this belongs in `CLAUDE.md` at the repo root once the project exists, so it persists across sessions.

---

## Who this is for

Matt Rodenbeck. Product motion and motion systems designer who ships software, with ten years of senior motion and 3D craft underneath. Targeting senior remote roles at product companies, design engineer and product designer titles included, with pay that follows the worker, relocating to the Pacific Northwest by June 2027. Compensation figures and negotiation posture live in `data/local/brief.md`, which never touches git.

He is technical. He built a commercial After Effects CEP panel driven by a local llama.cpp model across roughly 77 tools, with a 533-step self-test and a VRAM tier system. Do not explain basics. Do not over-scaffold.

## The positioning thesis — it constrains the build

The market prices "motion designer" low. It prices the **intersection** high: senior craft, plus a local generative AI pipeline, plus the ability to ship real software, plus pipeline and asset-management literacy.

Every surface leads with the intersection and uses motion work as proof. If a visitor files him as a motion designer in the first four seconds, the whole thing has failed.

## Three deliverables

### 1. Portfolio website

**Stack.** Suggest Astro with static output unless there is a reason otherwise. Content-driven, fast, good asset handling, trivial to deploy. Deploy to Cloudflare Pages, Netlify or Vercel. Plain HTML and CSS is also acceptable if he prefers total control. Ask before committing to a framework.

**Video.** Ten projects of motion work will not be served well from a static host. Plan for an external video host or CDN with local poster frames, and keep the content model host-agnostic so it can change.

**Structure, in order. The order is the strategy.**

1. **Hero.** The intersection statement. One sentence that says what he is, not what he does.
2. **What he builds.** AE Llama, the local ComfyUI pipeline, the Keynote extractor, the filename tool. This section comes before the reel deliberately.
3. **Selected work.** Curated motion and 3D, organized around the through-line of recurring flagship event brand systems carried across years. State turnaround times where they are impressive, since that advertises speed rather than endurance.
4. **Writing.** Technical posts. At least one on how the local pipeline works. This section is a differentiator, not filler.
5. **About and contact.**
6. **Archive**, deeper in, for anyone who digs.

**Content model.** Projects as markdown or JSON with frontmatter. Fields at minimum: title, year, client or event, role, discipline tags, tools used, turnaround where notable, a short description, hero still, gallery stills, video URL, and a process flag for storyboards and styleframes. He is collecting finals plus storyboards and stills for ten POWER projects, so the model needs to handle process material as a first-class thing rather than an afterthought.

**Non-negotiables.** Fast. Works on a phone. No layout shift on video. Accessible. The craft of the site is itself a portfolio piece, so sloppy implementation costs him credibility that the work would otherwise earn.

### 2. Job posting scraper

**Goal.** A repeatable process that surfaces genuinely relevant remote postings without him trawling boards daily.

**Approach — this matters.** Do not build a general scraper against LinkedIn or Indeed. Their terms prohibit it, they fight bots, and it breaks constantly. Build a **company-list-driven poller against ATS endpoints** instead, which is both more reliable and legitimate:

- Greenhouse, Lever, Ashby and Workable expose public per-company job JSON. A target list of companies plus their ATS slug gives clean structured data.
- RSS feeds and public APIs where offered.
- Remote-focused boards with documented feeds.
- Direct company careers pages for the handful that justify a bespoke parser.

The target list is the asset, not the scraper. He already needs one for outreach, so the two efforts share a source of truth.

**Filtering.** Encode the search protocol as scoring rather than binary rules, so borderline postings surface for judgment rather than being silently dropped:

- Genuinely remote-first, not "remote for now" or "hybrid, 3 days"
- Posted compensation, flagged when absent, scored against the target band in `data/local/brief.md`
- Title and description signal for the intersection. Weight terms like creative technologist, technical artist, pipeline, tooling, automation, generative, ComfyUI, Houdini, TouchDesigner, real-time
- Penalize pure production roles, agency hour-shops, and anything implying long-form grind work
- Seniority filter, exclude junior and mid
- Deduplicate across sources and across polls
- Track first-seen date, since freshness matters for response rates

**Output.** A local store, SQLite or JSON, plus a readable digest. A weekly digest is more useful than a live feed. Should be schedulable, and note that Claude Code supports scheduled tasks for exactly this.

**State.** Track applied, rejected, interested, ignored, so the same posting never resurfaces.

### 3. Cover letter generator

**Goal.** A unique, genuinely specific letter per application, generated from a job posting plus the target list entry, in his voice.

**Inputs.** Job posting text or URL, company record from the target list, and which proof points to lead with.

**Template architecture.** Modular blocks assembled per role rather than one template with holes:

- **Opening.** Names the specific thing about that company or role. Never "I am writing to apply for."
- **The intersection claim**, weighted by role type. AI video company gets the local pipeline first. Studio with an AI initiative gets tooling and integration first. Brand in-house team gets the craft and the event brand systems first.
- **One proof story**, selected to match. AE Llama, the local pipeline, the Keynote extractor, or a named event franchise carried across years.
- **Why remote is not a concession**, only where the posting hedges on it.
- **Close.** Direct, no grovelling.

**Voice.** This is the part most generators get wrong. He has a saved writing style profile and it must be enforced in the output:

- No em dashes. None. This is the strongest single signal.
- No semicolons, parentheses, ellipses, or bullet lists in prose.
- Comma-chained sentences, medium length.
- Contractions throughout.
- "But" as the main connector.
- No corporate vocabulary. No leverage, delve, circle back, streamline, robust, deep dive, align on.
- No "not X, but Y" construction.
- No formal sign-offs.

Build a lint step that fails the draft on any of the above rather than trusting generation. That check is cheap and it is what keeps the output from reading as machine-written.

**Output.** A draft he edits. Never auto-send, never auto-apply. The generator drafts, he decides.

## Repo shape

A monorepo is fine. Roughly:

```
/site          portfolio website
/scraper       ATS pollers, scoring, store, digest
/letters       template blocks, generator, voice lint
/data          target companies, project content, application state
```

`/data` being shared is the point. The target list feeds both the scraper and the letter generator, and project content feeds both the site and the proof stories.

## Ground rules

- Ask before choosing a framework or adding a dependency.
- Prefer boring, durable tooling. This runs for months, not once.
- Everything runs locally. No paid services without asking.
- Commit early and often, with real messages. This repo is also a public artifact of how he works, so its history is part of the portfolio.
