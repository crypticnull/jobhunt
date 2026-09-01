# Execution plan

## 1. What this is and why

This repo builds three things that share one data spine: a portfolio site, a job posting poller, and a cover letter generator. All three exist to land Matt a properly paid remote role before the June 2027 relocation to the Pacific Northwest, at the target band the private brief records. The market prices "motion designer" low and prices the intersection high, senior craft plus a local generative pipeline plus shipped software plus asset management literacy. Every surface this repo produces leads with that intersection and uses the motion work as proof. If any reader files him as a motion designer in the first four seconds, that surface has failed.

The plan inverts the brief's listing order. Applications compound over time and the site does not, and the site's heaviest assets, video finals and storyboards for the ten POWER projects, arrive on their own schedule outside this repo's control. So the target list ships in the first weekend, real postings land in SQLite by week three, the first scored digest arrives by week four, and the first application goes out by early November 2026, gated only on a stills-only site skeleton whose hero and What He Builds sections already pass the four-second test. The full portfolio, video hosting, and the writing section trail deliberately behind the application loop. The site never blocks an application.

The second audience for this repo is the hiring managers and senior engineers who will read it, because the build process is itself a portfolio piece. That is designed in, never reconstructed afterward. Decision records get written the day a decision is made, a fifteen-line log entry closes every work session, commit messages say why, and the root README carries a ten minute tour that tells a cold reader exactly what to verify and in what order, ending in `make demo`, one command that runs poll, score, digest, draft, and lint entirely offline against committed fixtures. No credentials, no network, no trust required. Every claim the repo makes about its own tooling is executable, and the private half of the job search, the real target list, the postings database, the sent letters, never touches git.

## 2. Architecture

### Repo layout

```
jobhunt/
  CLAUDE.md                      the binding brief
  README.md                      case study front door, ten minute tour
  CONTRIBUTING.md                commit style, ADR triggers, log rules
  Makefile                       make test, make poll, make digest, make demo, make site
  .github/workflows/ci.yml       tests, validate, lint, site build, Lighthouse budgets
  docs/
    decisions/                   ADRs, numbered, 25 line cap each
    log/                         one file per work session, 15 line cap
    naming.md                    filename token spec for project assets
    process.md                   the weekly application loop
    readme-standard.md           the documentation bar for packages and sibling repos
  scripts/
    log.sh                       prefills today's log entry from git log --since=midnight
    new-adr.sh                   stamps the next ADR number and template
    demo.sh                      full offline pipeline run against fixtures
  data/
    README.md                    the contract table: every store, its schema, one writer, its readers
    schema/                      JSON Schema per record type, plus db/schema.sql reference dump
    companies.example.json       committed, redacted, powers tests and demo
    scoring.json                 weights, term lists, comp band, thresholds
    voice/rules.json             banned lexicon, sign-offs, thresholds, two profiles
    projects/<slug>/index.md     project record, frontmatter plus body, beside its assets
    projects/<slug>/assets/      committed web derivatives, posters, stills, boards
    proof/<id>.md                proof story records
    pipelines/<slug>/index.md    pipeline record, ComfyUI graphs, node packs, tools
    pipelines/<slug>/assets/     annotated graph exports, posters, demo stills
    local/                       GITIGNORED, the actual search
      companies.json             real target list with notes and contacts
      postings.db                SQLite
      digests/                   weekly digest markdown
      letters/                   drafts and sent letters
  scraper/
    __main__.py                  poll, digest, mark, stats, add, add-posting, check, stale
    adapters/                    greenhouse.py, lever.py, ashby.py, workable.py,
                                 smartrecruiters.py, recruitee.py, rss.py
    store.py                     the ONLY writer of postings.db, applies migrations
    score.py                     pure functions over posting dict plus scoring.json
    digest.py                    weekly markdown digest
    salary.py                    regex comp extractor over description text
    migrations/0001_init.sql
    tests/fixtures/              recorded sanitized ATS responses, suite runs offline
  letters/
    __main__.py                  brief, lint
    voicelint.py                 compiler-style checker, path:line:col output
    assemble.py                  block selection per company category
    blocks/                      openings/, claims/, remote.md, closes/
    tests/samples/               one passing and one failing fixture per rule
  pipeline/
    naming.py                    token parser for docs/naming.md
    ingest.py                    probes media, extracts posters, writes frontmatter fields
    validate.py                  whole /data tree against /data/schema
    tests/
  site/                          Astro 7, static output, the only npm tree in the repo
    src/content.config.ts        collections over ../data/projects and ../data/pipelines, zod mirrors of the schemas
    src/components/Video.astro   native video, local poster, aspect-ratio box, zero CLS
  tools/
    check_drift.mjs              asserts each collection's zod schema matches its JSON Schema
```

### Data contracts

**Company record**, `data/local/companies.json`, private. A redacted `companies.example.json` is committed and powers tests and the demo. This is a deliberate reversal of earlier drafts that committed candid per-company notes publicly. A hiring manager at a listed company is the intended reader of this repo, and no company gets to read its own dossier. Nothing about the real list, priorities, or opinions is ever public.

```json
{
  "slug": "example-ai",
  "name": "Example AI",
  "ats": { "kind": "greenhouse", "board": "exampleai" },
  "category": "ai-video",
  "priority": 1,
  "lead_proof": "local-pipeline",
  "remote_notes": "",
  "contacts": [],
  "notes": "",
  "added": "2026-09-06",
  "last_reviewed": "2026-09-06"
}
```

`category` is the enum that drives letter assembly: `ai-video`, `studio-ai`, `product-inhouse`, `brand-inhouse`, matching the four target types from the positioning work. `ats.kind` covers `greenhouse`, `lever`, `ashby`, `workable`, `smartrecruiters`, `recruitee`, `rss`, `manual`.

**Postings store**, `data/local/postings.db`, SQLite via stdlib sqlite3, gitignored. Forward-only migrations as numbered SQL files applied by store.py using `PRAGMA user_version`, with a migration test that rebuilds from scratch and diffs against the committed `data/schema/db/schema.sql`. Status is a log, never a single mutable column, because a nine-month search wants its history.

```sql
CREATE TABLE postings (
  id INTEGER PRIMARY KEY,
  fingerprint TEXT NOT NULL UNIQUE,   -- source:external_id when given, else the content key
  content_key TEXT NOT NULL,          -- hash of company+normalized title, so dedupe survives an ATS migration
  company_slug TEXT NOT NULL,
  source TEXT NOT NULL,
  title TEXT NOT NULL, url TEXT NOT NULL, location TEXT,
  remote_class TEXT,                  -- remote | hybrid | onsite | unclear
  comp_min INTEGER, comp_max INTEGER, comp_found INTEGER,
  description TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, closed_at TEXT,
  score REAL, score_json TEXT,        -- per-rule breakdown, the explainability contract
  ruleset_version TEXT                -- so history can be rescored after weight tuning
);
CREATE TABLE status_log (
  posting_id INTEGER REFERENCES postings(id),
  state TEXT CHECK (state IN ('new','interested','applied','rejected','ignored','interview','offer')),
  noted_at TEXT NOT NULL, letter_path TEXT, note TEXT
);
CREATE TABLE poll_log (
  ran_at TEXT, source TEXT, company_slug TEXT,
  ok INTEGER, postings_seen INTEGER, new_postings INTEGER, error TEXT
);
```

**Scoring config**, `data/scoring.json`, committed. Weights for remote authenticity, comp against the target band with absence flagged rather than fatal, intersection terms (creative technologist, technical artist, pipeline, tooling, automation, generative, ComfyUI, Houdini, TouchDesigner, real-time), penalty terms for agency grind and junior or mid seniority, and a borderline threshold. The committed file carries structure and weights only. The actual comp band lives in gitignored `data/local/scoring.local.json`, merged at load, so the public repo never states the negotiation floor. Scoring ranks, it never drops. Tuning the search protocol is a diffable commit, and every score row carries its per-rule breakdown into the digest so a borderline posting arrives with the reason it is borderline.

**Project record**, `data/projects/<slug>/index.md` frontmatter, the record sitting beside its `assets/` so relative paths mean the same thing to the data contract and to the site's image pipeline. The ten POWER projects cleared to show are the initial content set: Quest 2024 animations, Quest 2025 key art and logo loop, Nitro Create 2025 branding, Nitro Create 2026 logo loop, Summit 2025 logo loop and branding expansion, PAG 2026 logo loop, Power Camp logo loop, HQ Soiree 2025 logo loop, the Company's Bill of Rights video, and Power For Good's Amberella motion graphics. `franchise` is a first-class field because Quest, Nitro Create, Summit and PAG carried across cycles is the curation strategy, ownership of a visual language rather than a pile of jobs. The eleventh record is personal rather than client work: the video game project, art direction and systems design in one artifact, its custom art generated through his own ComfyUI to Photoshop pipelines, `client` set to personal and `franchise` null.

```yaml
slug: quest-2025
title: Quest 2025 key art, animations and logo loop
franchise: quest
year: 2025
client: POWER Home Remodeling
role: Senior motion designer, brand system owner
disciplines: [3d, motion, brand-system]
tools: [cinema4d, redshift, after-effects]
turnaround: null              # stated only where genuinely impressive
summary: one sentence for cards
featured: true
hero: { src: assets/hero.jpg, width: 2560, height: 1440, alt: "" }   # paths relative to the slug directory
video: { provider: r2, mp4: [], hls: null, poster: assets/poster.jpg,
         width: 1920, height: 1080, duration: 24.0 }
stills: []                    # each entry {src, width, height, alt}
process: []                   # {kind: storyboard|styleframe|breakdown, src, width, height, alt, caption}
```

Width, height and duration are written by the ingest probe in `/pipeline`, never by hand, and `pipeline validate` refuses hand-edited values. That makes zero layout shift a property of the data, enforced by a numeric CLS budget in CI, rather than a hope. The video object is host-agnostic: the provider key plus local poster means switching hosts is one renderer branch and a re-upload. Media beyond the hero still is optional per record, so the site builds with partial assets while files arrive.

**Proof stories**, `data/proof/<id>.md`: `ae-llama`, `local-pipeline`, `keynote-extractor`, `dancekit`, `file-renamer`, `game-project`, `event-franchises`. Frontmatter carries `leads_for` (the company categories this story leads for) and `linked_projects` (slugs), so letters and the site state the same facts from one source. AE Llama, the 77-tool CEP panel with the 533-step self-test, leads for studios building AI capability. The 38-node local ComfyUI pipeline leads for AI video companies. The event franchises lead for brand in-house teams. The game project leads where a role wants art direction and systems design in the same person.

**Pipeline record**, `data/pipelines/<slug>/index.md`, frontmatter plus body. ComfyUI workflows and pipelines are portfolio content in their own right, a distinct content type beside projects, because a hand-built graph is exactly the artifact that separates him from the pure designers and the pure engineers at once. The body is the graph walkthrough: what each stage does and why the graph is shaped that way.

```yaml
slug: h3-i2v
title: MiniMax H3 image to video pipeline
kind: comfyui-graph           # comfyui-graph | node-pack | panel-backend | tool
status: production
nodes: 38
models: [minimax-h3, qwen-local, rtx-vsr]
hardware: RTX 5090, 64GB DDR5, fully local
graph: assets/graph.png            # annotated node-graph export, relative to the slug directory
workflow_json: null                # committed per graph, only where he chooses to share
demo: { provider: r2, mp4: [], poster: assets/poster.jpg, width: 1920, height: 1080 }
linked_proof: local-pipeline
writeup: null                      # slug of the writing post once it exists
```

Initial records: the 38-node MiniMax H3 image to video graph with local LLM prompt rewriting and RTX video super resolution, comfyui-dancekit from h3_dance_studio, AE Llama's hidden ComfyUI backend described without source, the ComfyUI to Photoshop asset pipeline that generated the game project's art, and the upscale, picture repair and character replacement graphs as each is cleaned up for showing. `workflow_json` is optional per record because sharing a graph is a per-graph call, and the site renders a download link only when the file exists. These records feed the What He Builds section, the pipeline breakdown pages, and the letter generator's proof selection for AI video companies, all from one source.

**Voice rules**, `data/voice/rules.json`, with two profiles. The strict `letter` profile enforces the full style: no em dashes, no semicolons, parentheses, ellipses or bullet lists in prose, no corporate lexicon, no not-X-but-Y construction, no formal sign-offs, contraction density checks. The light `repo` profile bans only em dashes and the corporate lexicon, so documentation can keep its parentheses. The same linter gates letters, proof stories, site copy and the writing posts.

### Module boundaries

One rule, stated in `data/README.md` and held by review: every store has exactly one writer, anyone may read through the published schema. The table is the architecture diagram.

| Store | Writer | Readers |
|---|---|---|
| data/local/companies.json | Matt, helped by `scraper add` | scraper, letters |
| data/projects, assets | Matt, helped by `pipeline ingest` | site, letters |
| data/proof | Matt | letters, site |
| data/pipelines | Matt | site, letters |
| data/scoring.json, data/voice | Matt | scraper, voicelint |
| data/local/postings.db | scraper/store.py only | letters read-only, digest |
| data/local/letters | letters | Matt |
| data/local/digests | scraper/digest.py | Matt |

No package imports another. The site never opens the database, the scraper never reads projects, letters never writes the database. Status changes go through `python -m scraper mark`, which Matt runs when he actually sends something.

### Tech stack and rationale

| Layer | Choice | Why |
|---|---|---|
| scraper, letters, pipeline | Python 3.12, stdlib only: urllib, sqlite3, json, argparse, unittest | Zero runtime dependencies means nothing rots over months of unattended running, and it matches the bar File Renamer already set in public |
| media probing | ffmpeg, already on his machine | He ships ffmpeg inside AE Llama, this is playing to strength |
| site | Astro 7, static output, pinned major, no experimental flags (needs sign-off) | Content collections plus astro:assets deliver typed frontmatter, build-time validation, and the responsive image work nearly free, so the saved evenings go to applications |
| site drift control | tools/check_drift.mjs in CI | Each zod schema and its JSON Schema are two expressions of one contract and must not diverge silently |
| deploy | Cloudflare Workers static assets (needs sign-off) | Unlimited free bandwidth, no pause-at-cap failure mode. Pages is in maintenance mode as of September 2026, and a repo built to be read by engineers should not start on a parked product. Netlify's credit system can pause a site mid-search, ruled out |
| video | Self-hosted MP4 and HLS on Cloudflare R2 free tier behind his domain (needs sign-off) | $0 at this catalog size, free egress, total poster control, zero third-party JS, native video plus CSS aspect-ratio is structurally zero CLS. The encode script becomes repo content. Bunny Stream at about $1 a month is the managed fallback, and the host-agnostic video object makes the switch trivial |
| scheduling | Windows Task Scheduler, nightly poll, Sunday digest | This runs on his Windows workstation, so cron was never an option. Claude Code scheduled tasks are the documented alternative |
| CI | GitHub Actions, whole suite offline from fixtures | Free on a public repo, never needs private data |

The ATS adapters build on documented endpoint patterns, smoke-tested live at the start of milestone 2. Greenhouse: `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true&pay_transparency=true`, remote is a text heuristic on `location.name`. Lever: `GET api.lever.co/v0/postings/{site}?mode=json`, with the structured `workplaceType` field and optional `salaryRange`. Ashby: `GET api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true`, with `isRemote`, `workplaceType` and the cleanest comp summary of the group. SmartRecruiters and Recruitee both have documented keyless endpoints with structured remote booleans. Workable's `apply.workable.com/api/v1/widget/accounts/{account}?details=true` is unofficial and has churned before, so that adapter ships last and is flagged as the likeliest to need maintenance. Structured pay data is the exception everywhere, so `scraper/salary.py`, a regex extractor over description text, is mandatory for the comp scoring to work. Remotive (hard cap of about four calls a day), We Work Remotely RSS and Himalayas serve as discovery feeds that suggest companies for the target list, never as primary sources.

## 3. Build sequence

Ordering principle: earliest useful output first. The digest is producing value by week four, applications by early November 2026, and the full portfolio fills in as assets arrive. Every milestone is a stable stopping point that leaves a working system, so a bad month at the day job stalls progress without stranding half-built work.

**1. Foundation.** One evening plus a short session.
Goal: repo spine, privacy split, and doc rails before any data exists, because a leaked file lives in git history forever.
Deliverables: directory skeleton with package README stubs, `.gitignore` covering `data/local/` from the first commit, a pre-commit guard refusing `.db` files, CONTRIBUTING.md with commit style and log rules, `scripts/log.sh` and `new-adr.sh`, ADR-0001 recording the ADR practice, ADR-0002 the privacy split, including the sanitization pass that moves the brief's salary figures and negotiation posture out of the public CLAUDE.md into `data/local/brief.md`, first commit of the milestone because the repo is public today with those figures already in it, ADR-0003 visible agent authorship, CI stub running unittest on push, the working branch `claude/jobhunt-claude-md-k8vpjj` folded into main and deleted.
Depends on: nothing.
Done when: a push runs green CI, `data/local/` is provably ignored, and the first log entry exists.

**2. Target list v1.** One weekend, research heavy, minimal code.
Goal: the asset both consumers feed on, 30+ companies across the four categories with verified endpoints.
Deliverables: `python -m scraper add <careers-url>` detecting ATS kind and board slug by probing the endpoint patterns, `companies check` probing every endpoint and reporting dead ones, `companies stale --days 60`, `data/local/companies.json` seeded from the existing target-company research, `companies.example.json` committed, `data/schema/company.schema.json` with a first-cut `pipeline/validate.py` wired into CI, `data/README.md` first cut of the contract table. Session opens with the ten-minute smoke test the research flagged: two known board slugs each against Greenhouse, Lever and Ashby, with the remaining patterns smoke-tested as each adapter ships, since the endpoint facts could not be live-probed during planning.
Depends on: Foundation.
Done when: `companies check` passes on 30+ real records and the example file validates.

**3. Scraper walking skeleton.** One weekend.
Goal: real postings in SQLite by Sunday night.
Deliverables: `store.py` with migration runner on `PRAGMA user_version` and the migration test against `schema.sql`, Greenhouse and Lever adapters (best documented, widest coverage), recorded sanitized fixtures, `poll` with fingerprint dedupe, first_seen and last_seen tracking, per-company error isolation, and `poll_log`.
Depends on: Target list v1.
Done when: two consecutive polls produce zero duplicates and the suite passes offline in CI.

**4. Scoring and digest.** One weekend. First continuously useful output.
Goal: a weekly digest that explains its own reasoning.
Deliverables: `data/scoring.json` v1 encoding the search protocol, `score.py` writing `score_json` and `ruleset_version` per posting, `salary.py` regex comp extraction with absence flagged, `digest.py` emitting strong, borderline and comp-absent lanes plus a source health footer listing any adapter that errored or returned zero twice running, postings already surfaced and unchanged or carrying applied, rejected or ignored status excluded from every lane, `mark` as the single status write path, `stats`, nightly poll and Sunday digest installed in Windows Task Scheduler, tests including the borderline-must-surface case.
Depends on: Scraper walking skeleton.
Done when: a real digest reads well on a phone and one deliberately borderline fixture posting appears in it with its reasons.

**5. Voice lint.** One or two evenings, slots into any gap after Foundation.
Goal: the deterministic gate for everything written in his voice, shipped before the first letter exists.
Deliverables: `voicelint.py` with `path:line:col rule-id message` output, exit 1 on hard fail and 2 on warnings, both profiles in `data/voice/rules.json`, hard fails for the mechanical rules and warnings for contraction density and sentence length, the letter profile blocking on any nonzero exit with the inline waiver comment as the only escape, the repo profile treating warnings as advisory, one passing and one failing fixture per rule, CI linting blocks and site copy with the repo profile.
Depends on: Foundation.
Done when: every rule has a fixture pair and the repo's own prose passes the repo profile.

**6. Site skeleton.** One weekend, after the framework and deploy sign-offs. This is the gate for the first application.
Goal: a deployed URL that passes the four-second test with zero video.
Deliverables: Astro 7 scaffold pinned with lockfile, content collections over `data/projects` and `data/pipelines` with `check_drift.mjs` in CI, the project and pipeline JSON Schemas committed beside their zod mirrors, hero with the intersection sentence, the proof records authored (`ae-llama`, `local-pipeline`, `keynote-extractor`, `dancekit`, `file-renamer`, `game-project`, `event-franchises`), What He Builds rendered from the pipeline and proof records, AE Llama, the H3 pipeline, comfyui-dancekit, the game project, the Keynote extractor and File Renamer above any reel, the first two pipeline records (h3-i2v, comfyui-dancekit) with graph images optional until exports arrive, three project entries stills-only, about and contact, deployed to Cloudflare Workers static assets on the domain bought now, Lighthouse budgets in CI with CLS at zero.
Depends on: Foundation. Runs in parallel with the scraper track.
Done when: the preview URL loads fast on a phone, and three cold readers each name what he is after four seconds with nobody saying motion designer unqualified.

**7. Letters live.** One weekend. First external payoff, targeted for early November 2026.
Goal: from digest row to lint-clean draft in one sitting, then the first sent application.
Deliverables: the `data/proof/` records brought through the letter-profile lint, `letters/blocks/` seeded from the existing content strategy notes, three openings, one intersection claim per company category, the remote paragraph included only when the posting hedges on remote (remote_class hybrid or unclear, or hedge phrases in the description), two direct closes, `python -m scraper add-posting <url-or-file> --company <slug>` writing a normal fingerprinted, scored row through store.py so referrals and postings from unpolled companies get letters identically, `python -m letters brief <posting-id> --lead <proof>` joining posting, company record, blocks and voice rules into one brief file drafted interactively in a Claude Code session he already pays for, lint gating the save on any nonzero exit, drafts landing in `data/local/letters/` with frontmatter linking the posting id, `mark applied` linking the letter path. No API key anywhere, nothing ever auto-sent.
Depends on: Scoring and digest, Voice lint, Site skeleton.
Done when: three real applications are sent, each linking the live site, each tracked in status_log.

**8. Loop on schedule.** Half a weekend plus cadence.
Goal: the weekly rhythm runs on schedule instead of willpower.
Deliverables: `docs/process.md`, Monday read digest, pick up to three, brief, draft, lint, send, mark, monthly `stats` snapshot into the log, the fifteen-minute minimum viable week documented: read the digest, mark statuses, done.
Depends on: Letters live.
Done when: two consecutive weeks run the loop without a manual poll.

**9. Adapter breadth and rot watch.** Ongoing, one evening at a time.
Goal: coverage grows as the target list demands, and rot is visible within a week.
Deliverables: Ashby and SmartRecruiters adapters next, then Recruitee, Workable last with its fragility documented, RSS adapter, discovery feeds wired as target list suggestions, nightly `sqlite3 .backup` copied to off-disk private storage plus a monthly JSON export of status_log so nine months of history cannot die with one disk, quarterly scoring review against actual response data, fixture refresh procedure for endpoint drift.
Depends on: Scoring and digest.
Done when: every ATS kind on the target list has an adapter or a documented manual path.

**10. Full work and video.** One to two weekends, gated on asset arrival, which is outside the repo's control.
Goal: all ten POWER projects and the game project live with video and process material, franchise through-line visible.
Deliverables: `docs/naming.md` token spec (`{franchise}_{year}_{deliverable}_{stage}_{vNN}.{ext}`), `pipeline ingest` parsing named drops, probing dimensions and duration, extracting posters, refusing malformed names with the corrected form printed, the full multi-format derivative factory deliberately deferred until volume earns it, R2 upload and encode script after sign-off, all ten records populated, franchise strips grouping Quest, Nitro Create, Summit and PAG across years, turnaround callouts where impressive including the single-day HVHZ 3D delivery, process galleries for boards and styleframes, the game project record populated from its own asset drop with stills, process material and a link to its pipeline breakdown, archive route.
Depends on: Site skeleton.
Done when: budgets stay green with real video and CLS holds at zero on a throttled mobile profile.

**11. Writing and launch.** One weekend plus writing evenings.
Goal: the differentiator section is real and the site is public on its own domain.
Deliverables: pipeline breakdown pages built from the pipeline records, each with the annotated node graph, a stage walkthrough, a demo clip where one exists, and a workflow JSON download where he shares it. Post one, "How the local ComfyUI pipeline works", published beside the h3-i2v breakdown it documents. Post two, "Polling ATS endpoints instead of scraping job boards", assembled from the log and ADRs. Both linted. Accessibility pass with keyboard nav, contrast and reduced-motion honored on loops. Production deploy on the domain attached at milestone 6, OG images, RSS for writing.
Depends on: Full work and video.
Done when: the domain resolves and the writing index sits in the section order the brief specifies.

**12. Sibling repos and case study close.** One or two evenings.
Goal: any entry point lands on the intersection within two sentences, and the repo verifies cold.
Deliverables: `docs/readme-standard.md` distilled from the h3_dance_studio and File Renamer READMEs, every package README passing it, iconik_meta_gen checked in its current state first and then the call put to Matt, write its README to the bar or keep it private until it earns one, cross-links between site and repos, pinned repos reordered, ten minute tour finalized and re-verified on a clean clone, `make demo` under a minute, and post three, "This repo as a case study", drawn from the ADRs, the log and `git log` itself.
Depends on: Writing and launch, Loop on schedule.
Done when: a clean clone runs `make demo` and `make test` green with no network.

Calendar anchors: first digest by week four (late September 2026), site skeleton live by late October, first applications early November, site launch around year end, then five clean months of application volume before June 2027.

## 4. The case study strategy

The capture happens as the work happens, with hard caps so it survives a full-time job.

**Commits.** Package-prefixed subjects (`scraper:`, `letters:`, `site:`, `pipeline:`, `tools:`, `data:`, `docs:`, and `repo:` for cross-cutting root files), imperative, body says why when the diff cannot, one working change per commit, ADR number cited when a commit executes a decision. Milestones get tags: `v0.1-scraper-live`, `v0.2-first-digest`, `v0.3-first-application`, `v1.0-site`. No squashing, the graph itself shows steady evenings-and-weekends cadence. The Claude co-author trailers stay in, recorded as ADR-0003, because directing agents well is a skill he is selling to exactly the AI companies on the target list, and the honest history proves it.

**Decision records.** Every sign-off choice becomes a numbered file in `docs/decisions` the day it is made: context, options, the call, the tradeoff accepted, 25 lines maximum. The privacy split ADR is the showcase piece, since it demonstrates judgment about tradeoffs rather than tool choice.

**Build log.** One file per session in `docs/log`, 15 lines maximum, prefilled by `scripts/log.sh` from that day's commit subjects: shipped, broke, decided, next. Dead ends stay in. The log is also the re-entry point that makes a two-week gap cheap to recover from, and the raw material for the writing posts, which get outlined at milestone close while context is hot and finished as prose later. Raw log entries never publish directly, the posts are edited work.

**The ten minute tour.** The root README scripts the cold read: minutes 0 to 2, the thesis and `git log --oneline`; 2 to 4, two named ADRs; 4 to 6, `make demo`, the offline pipeline against committed fixtures; 6 to 8, `make test` and the CI badge with its Lighthouse budgets; 8 to 10, the live site whose writing section matches the history just read.

**Real numbers.** Monthly `scraper stats` snapshots land in the log, postings seen, surfaced, applied, responses, so the closing case study post carries actual figures instead of adjectives, while the companies behind them stay private.

**Sibling repos.** h3_dance_studio and File Renamer already set the documentation bar and become the checklist in `docs/readme-standard.md`: problem in two sentences, a quick start that runs, a layout table, the exact test command, honest limits. They get cross-links and an opening-line voice check. iconik_meta_gen gets inspected and then either brought to the bar, worth an evening since it completes the Iconik and metadata proof, or made private until it is. Pinned repos on the GitHub profile get reordered so the intersection leads. AE Llama stays closed source, covered by description on the site and in proof-story blocks. The end state: a visitor entering through any repo finds the same positioning within two sentences.

## 5. Risks and how the plan absorbs them

**Privacy leak in a public repo.** The worst failure mode, because git history is forever and target companies are the readers. Absorbed structurally: `data/local/` is gitignored in the first commit before any data file exists, contacts and candid notes live only there, the committed example file is redacted, and a pre-commit guard refuses `.db` files and local paths. The live instance of this risk is the brief itself: the repo is public today and CLAUDE.md carries the current salary and the negotiation posture, so the Foundation sanitization pass is the first commit of the whole plan, and scrubbing the old figures from git history (or accepting that they stay) is an explicit call Matt makes at the same sitting.

**The day job notices the search.** A public repo that is plainly an active job search can be read by anyone, the current employer included. That is a choice, not an accident: employer references in public prose stay generic, the sanitization pass lands before anything else, and the visibility row in the decisions table is where Matt decides whether the repo stays public through the search or goes private until launch.

**Site polish eats evenings while zero applications go out.** The dependency graph gates the first application on the stills-only skeleton, never the full portfolio, and the early-November sent-application date is the metric reviewed monthly.

**ATS endpoints drift or die.** One small adapter per source, fixtures pin the known-good shapes so a refresh documents the change in the diff, per-company error isolation means one dead endpoint degrades to a digest note, and the source health footer makes rot visible within a week. Workable is flagged fragile from day one.

**Compensation data is mostly absent or textual.** Verified fact, structured pay is the exception on every platform. Comp absence is a flag and its own digest lane, never a drop condition, and the regex extractor is cheap by design. No investment in a clever comp parser.

**Scoring miscalibration buries good roles silently.** Scoring ranks and never drops, the borderline band always surfaces with per-rule reasons, `ruleset_version` allows rescoring history after tuning, and a suspiciously quiet week is visible in the raw counts.

**Asset arrival is the long pole.** It gates only milestone 10. Media is optional in the schema so the site builds partial, and until launch applications link the skeleton plus the existing repos, which already meet the bar.

**A bad month at the day job.** Every milestone is a stable stopping point, and the minimum viable week is fifteen minutes of digest reading and status marking. The digest arriving on schedule even in zero-code weeks is the motivation instrument.

**Framework churn.** Astro shipped two majors in 2026. Posture: pin v7, lockfile committed, ignore majors until after the search, no experimental flags. The Python side has nothing to churn.

**Single-disk loss.** Nightly `.backup` of postings.db plus monthly JSON export of status_log to private storage.

**Case study overhead swallows build time.** Hard caps: ADRs 25 lines, log entries 15, posts written only at milestone close from material that already exists.

**Kill criteria, written down now.** If ATS endpoints cover under 60 percent of the target list, stop writing pollers and lean on manual adds plus RSS. If three consecutive digests read as noise, collapse scoring to remote plus seniority and rank by recency. If the site slips past January, de-scope to a one-pager with hero, What He Builds and a reel link, and launch anyway.

## 6. Decisions Matt needs to make

| Decision | Recommendation | Why | Blocked until answered |
|---|---|---|---|
| Site framework | Astro 7, static output, pinned | Collections and image handling buy back evenings for applications. Honest alternative: plain HTML plus a small Python build script, a few extra weekends, and the generator becomes its own proof asset | Milestone 6 |
| Deploy host | Cloudflare Workers static assets, free | Unlimited bandwidth, no pause-at-cap. Pages is parked, Netlify's credit cap can pause a live portfolio | Milestone 6 deploy |
| Video hosting | Self-hosted on R2 free tier behind his domain, hand-tuned MP4s plus an HLS ladder for the longer pieces | $0, zero third-party JS, total poster control, and he already owns ffmpeg. Bunny Stream at about $1 a month is the managed fallback, Mux free caps at 10 assets, Vimeo and YouTube ruled out, pricing as of September 2026 | Milestone 10 video |
| Domain purchase, about $12 a year | Buy early | Application links and email stabilize, a workers.dev URL reads wrong at this seniority | Milestone 6 deploy |
| Python posture | Stdlib only, unittest, zero runtime deps | Nothing rots over months, matches the File Renamer precedent, and the restraint reads as judgment | Foundation CI stub |
| Repo visibility and privacy split | Stay public, `data/local/` private, redacted examples committed, sanitization pass first | The history is the portfolio and the search stays confidential, but the repo is public today with the brief's figures in it, and public also means the day job can read it | Foundation, first commit |
| Scheduler | Windows Task Scheduler, Claude Code scheduled tasks as alternative | It is a Windows workstation, and misses are tolerated by weekly cadence | Milestone 4 |
| Letter drafting engine | Brief files drafted in Claude Code sessions, lint gates the save | No new spend, no API key in the toolchain, he edits every draft anyway | Milestone 7 |
| Visible agent authorship | Keep trailers, tag agent sessions in the log | On-thesis for AI company readers, and hiding it would be dishonest | ADR-0003 at Foundation |
| iconik_meta_gen | Inspect, then write its README to the standard or make it private | It completes the metadata literacy proof if brought to the bar | Milestone 12 |
| Workflow JSON sharing | Publish the H3 graph JSON, keep client-tied graphs private, decide per graph | A downloadable working graph is rare, verifiable proof of pipeline literacy, and per-graph control keeps anything sensitive out | Milestone 11 pipeline pages |
| Game project repo | Public repo once it meets the readme standard, linked from the site either way | It is the one artifact showing art direction, systems design and the generative pipeline together | Milestone 12 cross-links |
| Analytics | None at launch | Nothing to consent-banner, and responses are the metric that matters | Launch |

## 7. First moves

**Session one, an evening.** The sanitization pass goes first, because the repo is public right now: move the brief's salary figures and negotiation posture from CLAUDE.md into `data/local/brief.md`, commit, and make the history call, scrub the old figures or accept them, in the same sitting. Then fold `claude/jobhunt-claude-md-k8vpjj` into main and delete it. Create the directory skeleton with package README stubs. Commit `.gitignore` covering `data/local/` and the pre-commit guard, then CONTRIBUTING.md, `scripts/log.sh`, `scripts/new-adr.sh`, and ADRs 0001 through 0003 for the ones Matt signs off tonight: the ADR practice itself, the privacy split, and agent authorship. Stand up the CI stub. Close with the first log entry. The repo now captures its own story from commit one.

**Session two, the first weekend.** Start with the ten-minute endpoint smoke test, two known board slugs each against Greenhouse, Lever and Ashby, since the endpoint research could not be live-probed during planning and any mismatch is a docs-drift note, never a design problem. Then build `scraper add` with ATS detection and `companies check`, and spend the rest of the weekend where the value is: seeding `data/local/companies.json` with the first 30 targets from the existing target-company research across all four categories, committing the redacted example, and writing the first cut of the contract table in `data/README.md`. By Sunday night the shared asset exists, both consumers have their source of truth, and milestone 3 has everything it needs to put real postings in SQLite the following weekend.