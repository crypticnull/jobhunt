# Search protocol

```
version: 1.1
date: 2026-09-05
status: final
owner: Cowork agent
consumer: opportunity scraper (coding project)
machine twin: scoring.json (same rules as data, must stay in sync)
```

## Purpose

Rules for which job listings are worth Matt's time. The scraper collects, normalizes, gates, scores and sorts. Matt only ever sees the apply pile and the review pile. Everything else is logged with a reason so the rules can be tuned at the Nov 16 checkpoint.

Two hard gates run first. A listing that fails either gate is dropped regardless of score. Then a 100-point score, deductions for underpaid tells, and a threshold sort into piles.

The scraper never decides to apply. It decides what Matt looks at.

## The curriculum, pointed forwards

Added 2026-09-05 at Matt's request, and the direction matters. The first version of this derived a study list from the postings, jobs to curriculum. He asked for the opposite: the curriculum should influence which jobs surface, because the point is to align what he is learning with the jobs the learning leads to, one funnel with a procedure to follow.

So `scoring.json` carries a `curriculum` block with a vocabulary and a set of `targets`, currently product-motion and web-motion, which is the product animation and motion systems direction. A posting asking for those scores up to 5 points **whether or not Matt can claim the skill yet**. That is the whole idea: the job asking for what he is studying is the job the studying is for, and a scale that only rewards what he already has can only ever find him his current job again.

Those 5 points came from company tier, halved from 10 to 5, on his own argument that the top 100 is a lagging indicator. Where a company sits on a list he would not have written matters less than whether the job is the one he is training for. The pile thresholds came down 5 with it, apply to 65 and review to 45, so the rebalance changes which postings win rather than how many clear.

Backwards, the same vocabulary counted against `data/skills.json` gives the study list. The nightly job writes it to `data/curriculum.md` and commits it, so it is versioned and the diff shows what the market started asking for, and it is in the digest and available as `python -m scraper curriculum`. A term is a gap when the target postings ask for it and the skills file cannot claim it, and gaps rank by how often the market asks. Learning down that list moves the piles, because it is the same vocabulary on both ends.

`skills.json` requires evidence on every entry, a project slug, a proof record or the resume. A skill claimed without evidence removes itself from the study list and never gets learned.

## The two guiding principles

Stated by Matt on 2026-09-05 and they outrank everything below. **Remote**, so he can live where he likes without a commute, which means location-agnostic pay matters as much as a remote job title, because a location-adjusted employer turns a move to a cheaper place into a pay cut. And **no longform animation**, which is why the target is product animation and motion systems, motion embedded in a product rather than delivered as a film.

Both were only half encoded before that date. The remote gate was already firm. The longform rule caught a fixed-fee bid for a full animated piece and missed a staff job on a feature or a series, and nothing in the ruleset scored product animation or motion systems at all.

## Who this is for

Matt Rodenbeck. Market-facing title Creative Technologist. Currently a senior motion designer in Pennsylvania, moving to Washington or Oregon in June 2027. Remote only. Base floor $130,000. Target $150,000. Ask $160,000 to $170,000 at AI companies. See the plan for the positioning thesis, the short version is that the intersection of senior 3D and motion craft, a working local generative AI pipeline, shipping software with agentic coding, and pipeline literacy is what's being sold, and motion design alone is what's being avoided.

## Sources, in priority order

1. Careers pages of companies in `targets.csv`, through their ATS. These are the highest-value listings and the ones where unlisted salary is tolerable. Greenhouse, Lever and Ashby all expose public JSON, so poll those directly rather than scraping HTML.
   - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
   - Lever: `https://api.lever.co/v0/postings/{company}?mode=json`
   - Ashby: `https://api.ashbyhq.com/posting-api/job-board/{org}` (public postings, includes compensation when the company enables it)
   - Workday, SmartRecruiters, Rippling and custom boards need per-company handling. Log them as `source_type: manual` until a fetcher exists.
2. Aggregators with a remote filter: Wellfound, Otta / Welcome to the Jungle, We Work Remotely, Working Nomads, Remotive, Remote OK. LinkedIn only via the public job search pages and only within its terms, never with an authenticated session.
3. Community boards, manual or semi-manual: Motionographer jobs, the ComfyUI Discord jobs channel, the aescripts community, Motion Design Slack groups, Creative Technologist listings on The Dots. These are low volume and high signal, a weekly manual sweep is fine for v1.

Seed lists live in `data/seeds/*.txt` as `category | careers url | name`, with an optional fourth field for the headquarters as `City, ST`. The nightly job runs `scraper import data/seeds` before polling and skips any company already on the list, so a list dropped in that directory is taken in on its own. Added 2026-09-05, when a count of the corpus put the yield at 0.8% and showed the binding constraint was seed coverage rather than filter quality: the scraper can only find what it is pointed at, and it was pointed at 88 companies.

A second list went in on 2026-09-05, across the western states, weighted to ones nobody would put on a top 100. Two reasons. Matt moves to Washington or Oregon in June 2027, so a company already in the west is worth knowing about early. And the top 100 is a lagging indicator: every company on it was small once, and the roles worth having are often posted before a company is famous. Its first version led with fifteen animation, VFX and title studios on the reasoning that they were closest to Matt's own discipline. That was the wrong reasoning and he said so the same day: those studios are place-based and longform, which is both principles broken at once. They were removed before anything was imported. What remains is mountain-west and coastal product companies and western brands running real in-house creative teams.

Two more lists went in with it. A remote-first list of companies that are all-remote by construction or known to pay the same wherever you sit, which is the one that serves the first principle directly, and a Midwest list, because he can work from anywhere and the point is coverage rather than a bet on a city.

Discovery's caps went up the same day, from 15 boards and 30 postings a night to 40 and 80, and moved out of the function signature into `scoring.json` so they can be tuned without a code change. The old numbers were written when the list was ten companies long.

Company boards first, aggregators second. Aggregators are where most fake-remote and underpaid listings come from, so they get the same gates but a lower prior.

## Normalization

Every listing becomes one record with these fields before any rule runs. Missing fields are `null`, never guessed.

| field | type | notes |
|---|---|---|
| `id` | string | stable hash of `source + external_id` or `source + url` |
| `source` | string | `greenhouse`, `lever`, `ashby`, `wellfound`, `linkedin`, `manual`, etc |
| `url` | string | canonical listing URL |
| `company` | string | as posted, then matched against `targets.csv` by normalized name and domain |
| `company_tier` | 1–4 or `null` | from `targets.csv`; `null` if unknown |
| `company_size` | int or `null` | headcount if the source or targets file has it |
| `title` | string | as posted |
| `title_norm` | string | lowercased, punctuation stripped, seniority words kept |
| `posted_at` | date or `null` | |
| `first_seen`, `last_seen` | datetime | scraper's own bookkeeping |
| `location_raw` | string | exactly as posted |
| `remote_claim` | `remote` / `hybrid` / `onsite` / `unclear` | from location and title fields only |
| `states` | list of two-letter codes or `null` | parsed from body and location; `null` means no list; `["US"]` means nationwide |
| `salary_min`, `salary_max` | int or `null` | in USD, annualized |
| `salary_period` | `year` / `hour` / `null` | as posted, before annualizing |
| `salary_source` | `posted` / `ats_field` / `null` | |
| `employment_type` | `full_time` / `contract` / `contract_to_hire` / `freelance` / `null` | |
| `description_text` | string | plain text, HTML stripped, for keyword rules |
| `contact_hint` | string or `null` | a named person from the posting, the team page, or the ATS `hiring_manager` field |

The company record carries two more fields as of 2026-09-05. `hq` is the headquarters as `City, ST` or null, printed on every apply row, because a company already in the Pacific Northwest is worth noticing while the move is being planned. `pay_model` is `same-everywhere`, `location-adjusted` or `unknown`, default unknown. Location-adjusted pay is what decides whether the move to Washington or Oregon costs money, so it is a field that can gate and score rather than a line in a memo. The digest prints it on every apply row so it gets asked on the first call instead of discovered at offer stage.

Dedup by `id`, then by `company + title_norm` across sources within 14 days, keeping the company-board version when both exist.

## Gate 1: remote is real

Pass, flag, or fail. Fail drops the listing. Flag passes at half marks on the remote signal and carries a reason string Matt sees.

**Pass** requires all of:
- `remote_claim` is `remote`, from the location field or the title.
- No fake-remote phrase anywhere in the body. The list is in `scoring.json` under `remote.fail_phrases`. The core ones: hybrid, on-site, onsite, in-office, in office, remote for now, remote to start, initially remote, occasional office, days in the office, days per week in, commuting distance, local candidates, within N miles, must be located in, relocate to.
- State list is `null`, nationwide, or contains PA and at least one of WA or OR.

**Fail** on any of:
- `remote_claim` is `hybrid` or `onsite`.
- Any fail phrase present.
- State list exists and does not include PA. He starts the job from Pennsylvania, so this is not negotiable for v1.
- A single named city or metro with no state list and language like "based in", "located in", "must reside".
- The location names another country and no US marker. Checked against the location only, never the body, because a US role can perfectly well mention EMEA teams. "Remote - US, Canada" passes; "Remote - LATAM" and "Electrical Design Engineer (Estonia)" do not. Added 2026-09-05 after those turned up inside the remote target set.

**Flag** (pass at half marks, reason attached) on:
- State list includes PA but neither WA nor OR. State lists change and it can be asked on the first call.
- Location reads like "Remote (San Francisco)" or "Remote - New York" with no state list and no residency language. Usually a payroll default, not a requirement.
- `remote_claim` is `unclear` but the body says remote and no fail phrase is present.
- Time zone requirements tighter than "US time zones". Pacific-only is fine for someone moving to the Northwest and earns the full remote marks, Eastern-only is a flag, not a fail.

## Gate 2: comp isn't insulting

Annualize first. Hourly times 2080. Ranges keep both ends. Gate on `salary_max`, because that's the number a negotiation can reach. Score on the midpoint, because that's the number they'll open with.

**Pass**
- `salary_max` ≥ 130,000.
- Salary not posted, and `company_tier` is 1, 2 or 3, or `company_size` > 200.

**Flag** (passes, low comp score, reason attached)
- `salary_max` between 110,000 and 129,999. Worth a look only at tier 1 or 2 where equity and a fast band correction are plausible. At tier 3 or 4 this is a soft drop, so score it but push it to review, never apply.

**Fail**
- `salary_max` < 110,000.
- Hourly under $85 for contract or freelance, annualized. The floor is firm, so a contract posting that lists an annual figure is held to the same number.
- Salary not posted, company not in `targets.csv`, and size unknown or under 200. Most states with remote-hiring companies require posted ranges now, so a remote-US listing with no range is itself a signal.
- Any unpaid test project, take-home or "design exercise" described as longer than two hours, or any spec work.

Log every gate-2 fail with its reason. The Nov 16 checkpoint reviews the `unlisted_salary_unknown_company` bucket specifically, because that's the rule most likely to be throwing away good listings.

## Underpaid tells

Each match subtracts 3 from the final score. Cap the total deduction at 15. The full phrase list is in `scoring.json` under `deductions`. The intent behind each:

- "content creator", "social media videos", "short-form content", "10+ videos a week", or any per-week output quota: volume shop.
- "wear many hats", "fast-paced environment", "scrappy", "startup mentality" without a posted band: underpaid by design.
- "rockstar", "ninja", "guru", "wizard": tells you who wrote the listing.
- "junior", "mid-level", "associate", "coordinator" in the title: wrong level.
- "unlimited PTO" or "competitive salary" standing in where a number should be.
- Agency vocabulary: "account", "client deliverables", "billable", "utilization".
- "AI video editor", "AI content", "generate content at scale": churn framing, the opposite of the intersection.
- Staffing firm with "confidential client" or "our client" and no band.
- "must be comfortable with tight deadlines" or "high volume" paired with no band.

Deductions never drop a listing on their own. They sort it lower so it's read later or not at all.

## Disqualifiers

Drop, with reason logged. Distinct from gates because they're about the work, not the terms.

- Pure editing roles: "video editor", "editor" as the primary title with no motion, 3D, design or technical component.
- Engineering roles wearing the same words. "Design Engineer" qualified by electrical, mechanical, civil, structural, precast, controls, HVAC, hardware or similar. Added 2026-09-05: the title match was catching civil and electrical engineering and polluting the highest-value tier, with Controls Design Engineer (Electrical), Electrical Design Engineer and Precast Design Engineer all live in the remote target set.
- Pure UX by title: "user experience designer", "UX/UI designer", "product designer (UX". These were already listed as body phrases, but disqualifiers match phrases against the body only, so a posting titled User Experience Designer was never dropped. It mattered little while no product title could tier, and it matters now that one can.
- Longform animation in any form, staff or freelance. Fixed-fee bids for a full animated piece, and as of 2026-09-05 also feature film, animated feature, episodic, theatrical, television or broadcast series work, plus the film-pipeline titles that only exist to serve it: character animator, storyboard artist, layout artist, compositor, roto, matchmove. This is one of the two guiding principles and it is absolute.
- Relocation required or "relocation assistance provided" as a substitute for remote.
- Travel over 10%.
- Contract-to-hire with a conversion salary below the floor, or no conversion salary stated.
- Postings older than 30 days with no repost. `posted_at` older than 30 days and `last_seen` more than 7 days ago.
- Roles whose primary requirement is a discipline he doesn't have and can't credibly bridge: pure UX/UI product design, pure brand strategy, pure ML research, pure sound design.

**Flag, don't drop**
- Unreal or Unity as the primary tool. Technical Artist listings often want a game engine. The eye and the pipeline thinking transfer, the engine doesn't, but it's worth Matt's call.
- Web frontend terms, react, typescript, frontend, front-end, **only where the title has not already earned tier A or B**. Revised 2026-09-05. Every design engineering posting names React and TypeScript, so flagging them sent the tier being promoted straight to review, which defeated the promotion. Where the title is untiered and the body is mostly frontend, the flag still stands and Matt decides.

## Score

100 points. Gates already passed. Half marks on remote if flagged.

| signal | max | rule |
|---|---|---|
| Remote clean | 25 | Pass with no flag and Pacific hours, or a state list naming WA or OR: 25. Pass with no flag, US-wide: 22. Pass with any flag: 12. |
| Compensation | 20 | Midpoint ≥ 150k: 20. 130k–150k: 15. Unlisted at tier 1–3: 10. Unlisted, size > 200, no tier: 8. Flagged 110k–130k: 5. |
| Intersection asks | 20 | 5 points per leg mentioned in the body, max 4 legs. Legs and their keyword lists are in `scoring.json`. A leg counts once no matter how many keywords hit. |
| Title fit | 15 | Tier A title: 15. Tier B: 10. Tier C: 5. Lists below and in `scoring.json`. |
| Company tier | 5 | Tier 1: 5, 2: 4, 3: 3, 4: 2, unknown: 1. Halved 2026-09-05; the other 5 went to the curriculum. |
| Curriculum | 5 | Two or more `curriculum.targets` areas in the body: 5. One: 3. Scored whether or not Matt can claim the skill. |
| Freshness | 5 | Posted within 7 days: 5. Within 14: 3. Otherwise 0. |
| Human findable | 5 | `contact_hint` present: 5. |

The leg term lists were cut back hard on 2026-09-05, after the first real digest put an Economist, a PCB Layout Engineer and a Software Engineer for Trainium in the apply pile. The discovery config had already written the reason down weeks earlier, in its own note: the scoring legs are far too broad, rendering matches every backend job, and generative ai is boilerplate. That lesson had only ever been applied to discovery. Bare `3d`, `modeling`, `modelling` and `rendering` are gone, because economic modeling, threat modeling and server-side rendering were all scoring the 3d leg. Bare `generative` and the phrase `generative ai` are gone for the same reason. And `runway` is gone because it is a company name, so every Runway posting was scoring a generative leg for its own letterhead.

**Intersection legs** (5 each, max 20)
- `3d`: cinema 4d, c4d, redshift, octane, 3d, modeling, modelling, lighting, texturing, rendering, houdini, blender
- `motion`: after effects, motion design, motion graphics, animation, compositing, premiere, brand motion
- `generative`: generative, diffusion, comfyui, stable diffusion, flux, wan, text-to-video, image-to-video, img2vid, ai video, ai image, gen ai, genai, lora, controlnet, upscaling
- `software`: python, javascript, typescript, extendscript, cep, plugin, panel, scripting, automation, api, rest, node, tooling, agentic, llm, local models, llama.cpp, ollama
- `pipeline`: pipeline, asset management, mam, dam, metadata, taxonomy, naming convention, iconik, frame.io, workflow, render farm, versioning
- `product`: prototyping, prototype, figma, design system, design systems, component library, interaction design, design tokens. Added 2026-09-05. These are the terms the remote target set actually runs on, prototyping in 64.5% of it, Figma 42.6%, design systems 41.4%, and design systems carries the highest median comp of any term measured. It scores as intersection, and deliberately does not satisfy the tier B leg gate.

**Title tiers**
- Tier A (15): creative technologist, technical artist, design technologist (zero occurrences in 6,425 postings as of 2026-09-05, kept here because it costs nothing and would be a bullseye, removed from the discovery term lists where it only spent match budget), creative engineer, motion design engineer, creative developer, generative ai designer, generative ai artist, ai creative lead, ai creative director, creative ai engineer, pipeline td, motion technologist, technical director (motion or design context)
- Tier B (10): motion designer, senior motion designer, lead motion designer, 3d motion designer, 3d artist, 3d generalist, art director, design engineer, **product designer, brand designer, visual designer**, when the body also hits the `generative` or `software` or `pipeline` leg

  Product and brand titles added 2026-09-05. Product Designer is 130 of the corpus against Motion Designer's 25, it is where the remote volume and the pay are, and roughly 29 of the 59 remote target roles are at AI video and image companies where those titles are how the work is advertised. Luma posted Creative Technologist twice and also Visual Designer Product. The leg gate is what reconciles that with the thesis: `product` alone never earns a tier, so a Product Designer role tiers at an AI video company that wants generative or pipeline work and does not tier at a bank. Pure UX is still dropped outright.
- Tier C (5): motion designer, senior motion designer, 3d artist, animator, when the body hits none of `generative`, `software`, `pipeline`

## Piles

- **Apply**: score ≥ 65 **and a title tier**. Added 2026-09-05: the apply pile is what the letter generator reads, and a posting whose title does not fit is not one Matt can write a credible letter for, whatever the body scores. It is how an Economist and a PCB Layout Engineer reached apply on generic body language. They still reach review. Goes to the cover letter generator with the listing record, the tier and the proof-point lead for that tier (see `proof-points.json` when it exists, until then tier 1 leads with the ComfyUI pipeline, tier 2 with AE Llama, tier 3 with the tooling record, tier 4 with franchise ownership).
- **Review**: 45–64, plus anything with a flag regardless of score. Matt skims on Mondays.
- **Logged**: under 50, and every gate fail and disqualifier, with a reason string.
- **Relevance floor**, added 2026-09-05 and tightened the same day. A posting is relevant when the title tiers, or the body hits a **craft** leg: `3d`, `motion`, `generative` or `product`. `software` and `pipeline` are deliberately excluded, because they support a creative role rather than define one and every backend job in the corpus hits them. The first version accepted any leg, and the first real run put 894 postings in a pile led by LLM, CI/CD and GraphQL, which is a software job board rather than a shortlist. A posting with neither a tiered title nor a craft leg is logged whatever it scores. Remote 22 plus comp 20 plus a tier 1 company plus freshness is 57, over the review threshold, on a posting about nothing Matt does, which is how a Backend Engineer at a good company was reaching the review pile. With a cap of 40 a week that is how the pile fills with work he would never take. Comp and company prestige can carry a posting, but only after it is about something.

Both caps are 100 per week as of 2026-09-05, up from 12 on apply and 40 on review. A genuinely good match should not be held back by an arbitrary number when the digest is where the fine-toothed comb runs. The apply cap still sorts by tier then score, so the order is meaningful even when the number is not binding, and the generator is still only ever run on the letters Matt chooses to send. Matt sends 5 to 8 a week, all custom, the cap keeps the generator from producing letters nobody reads.

## Output record

Every listing that passes the gates is written with this shape. The generator reads it. Field names are final.

```json
{
  "id": "greenhouse:runwayml:4567890",
  "source": "greenhouse",
  "url": "https://...",
  "company": "Runway",
  "company_tier": 1,
  "title": "Creative Technologist, Video",
  "posted_at": "2026-09-03",
  "location_raw": "Remote - US",
  "remote": { "result": "pass", "flags": [] },
  "comp": { "result": "pass", "salary_min": 140000, "salary_max": 180000, "period": "year", "flags": [] },
  "employment_type": "full_time",
  "legs_hit": ["generative", "motion", "software"],
  "title_tier": "A",
  "score": { "remote": 25, "comp": 20, "intersection": 15, "title": 15, "company": 10, "freshness": 5, "human": 5, "deductions": 0, "total": 95 },
  "deduction_hits": [],
  "pile": "apply",
  "proof_lead": "comfyui_pipeline",
  "contact_hint": "Jane Doe, Head of Creative",
  "status": "new",
  "first_seen": "2026-09-08T14:02:00Z",
  "last_seen": "2026-09-08T14:02:00Z"
}
```

`status` moves through `new`, `reviewed`, `applied`, `screen`, `loop`, `offer`, `rejected`, `skipped`. Matt sets it, the scraper never overwrites it once it's past `new`.

## Weekly digest

Every Monday morning, one file or message with: count of new listings by source, apply pile sorted by tier then score, review pile with flag reasons, counts of drops by reason, and, added 2026-09-05, an "Earning their poll" section naming any company that has been polled fifteen or more postings and cleared none of them. That section reports and never acts: a company that should be posting design roles and is not may be a title filter miss rather than a dead company, so it prints the names and the prune command and stops. Shortening the target list is Matt's call, not a scheduled job's. The drop-reason counts are what get the rules tuned. That digest folds into the Monday report Matt already gets.

## Tuning schedule

- Sep 2 to Sep 6: collect only, compressed from a month on 2026-09-02 because Matt does not expect to still be in his current job in two. Use the first digests to check the gates aren't throwing away obvious fits. A posting scoring 85 or better is named in the digest anyway; it will not wait.
- Sep 6: first apply pile, the very first digest.
- Oct 5 checkpoint: if tier 1 and 2 response rate is under 10% after 20 applications, the problem is the materials, not the rules. If the apply pile is thin, loosen `unlisted_salary_unknown_company` first, then title tier B, in that order. Never loosen gate 1.

## Open questions for Matt

- Any companies where a state-list flag should be ignored because he'd move early for them?

Answered 2026-09-02: Pacific-only outscores US-wide, and $85/hour is a firm floor for contract work.
