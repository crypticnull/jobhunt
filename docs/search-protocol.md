# Search protocol

```
version: 2.0
date: 2026-09-05
status: final
owner: Cowork agent
consumer: opportunity scraper (coding project)
machine twin: scoring.json (same rules as data, must stay in sync)
```

## Purpose

Rules for which job listings are worth Matt's time. The scraper collects, normalizes, gates, scores and sorts. Matt only ever sees the apply pile and the review pile. Everything else is logged with a reason so the rules can be tuned at the Oct 5 checkpoint.

Two hard gates run first. A listing that fails either gate is dropped regardless of score. Then a 100-point score, deductions for underpaid tells, and a threshold sort into piles.

The scraper never decides to apply. It decides what Matt looks at.

## The curriculum, pointed forwards

Added 2026-09-05 at Matt's request, and the direction matters. The first version of this derived a study list from the postings, jobs to curriculum. He asked for the opposite: the curriculum should influence which jobs surface, because the point is to align what he is learning with the jobs the learning leads to, one funnel with a procedure to follow.

So `scoring.json` carries a `curriculum` block with a vocabulary and a set of `targets`, currently product-motion and web-motion, which is the product animation and motion systems direction. A posting asking for those scores up to 5 points **whether or not Matt can claim the skill yet**. That is the whole idea: the job asking for what he is studying is the job the studying is for, and a scale that only rewards what he already has can only ever find him his current job again.

Those 5 points came from company tier, halved from 10 to 5, on his own argument that the top 100 is a lagging indicator. Where a company sits on a list he would not have written matters less than whether the job is the one he is training for. The pile thresholds came down 5 with it, apply to 65 and review to 45, so the rebalance changes which postings win rather than how many clear.

Backwards, the same vocabulary counted against `data/skills.json` gives the study list. The nightly job writes it to `data/curriculum.md` and commits it, so it is versioned and the diff shows what the market started asking for, and it is in the digest and available as `python -m scraper curriculum`. A term is a gap when the target postings ask for it and the skills file cannot claim it, and gaps rank by how often the market asks. Learning down that list moves the piles, because it is the same vocabulary on both ends.

The vocabulary matcher counts plurals as of 2026-09-05, so "design systems" and "micro-interactions", which is how product postings write them, score. A regex-form term such as the one for llm is claimed by its readable form, and a claimed skill retires any term it matches, so "stable diffusion" retires "diffusion". Bare "canvas" and bare "spline" left the vocabulary because they scored a blank canvas and spline interpolation, and unreal, unity and vfx left the study list because the second principle rejects that work.

Discovery learned the same vocabulary the same day. Its title patterns and require-any terms carried no product-motion or design-engineer vocabulary, so a Design Engineer or Senior Product Designer in an open feed was dropped before it could add a company, and the mechanism ADR-0009 relies on to find companies early was blind to the direction. Design engineer, design systems, interaction design, product design and design technologist are titles now, figma, design system, design tokens, component library, prototyping, lottie, rive, framer motion and gsap are terms, and every engineering-discipline design engineer is excluded by title so a mechanical one with "prototyping" in the body does not ride in.

`skills.json` requires evidence on every entry, a project slug, a proof record or the resume. A skill claimed without evidence removes itself from the study list and never gets learned.

## The two guiding principles

Stated by Matt on 2026-09-05 and they outrank everything below. **Remote**, so he can live where he likes without a commute, which means location-agnostic pay matters as much as a remote job title, because a location-adjusted employer turns a move to a cheaper place into a pay cut. And **no longform animation**, which is why the target is product animation and motion systems, motion embedded in a product rather than delivered as a film.

Both were only half encoded before that date. The remote gate was already firm. The longform rule caught a fixed-fee bid for a full animated piece and missed a staff job on a feature or a series, and nothing in the ruleset scored product animation or motion systems at all.

## Who this is for

Matt Rodenbeck. Market-facing title Creative Technologist. Currently a senior motion designer in Pennsylvania, moving to Washington or Oregon in June 2027. Remote only. The base floor, the target and the ask live in data/local/brief.md and data/local/scoring.local.json, and every number that describes the comp band is null in the public ruleset. See the plan for the positioning thesis, the short version is that the intersection of senior 3D and motion craft, a working local generative AI pipeline, shipping software with agentic coding, and pipeline literacy is what's being sold, and motion design alone is what's being avoided.

## Sources, in priority order

1. Careers pages of companies in `data/companies.json`, through their ATS. These are the highest-value listings and the ones where unlisted salary is tolerable. Greenhouse, Lever and Ashby all expose public JSON, so poll those directly rather than scraping HTML.
   - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
   - Lever: `https://api.lever.co/v0/postings/{company}?mode=json`
   - Ashby: `https://api.ashbyhq.com/posting-api/job-board/{org}` (public postings, includes compensation when the company enables it)
   - Workday, SmartRecruiters, Rippling and custom boards need per-company handling. Log them as `source_type: manual` until a fetcher exists.
2. Remote job feeds with a documented API or RSS: Remotive, We Work Remotely, Himalayas, Jobicy, Arbeitnow, RemoteOK, and the month's Hacker News "Who is hiring" thread. These are discovery sources: a posting that names a creative-technical role and links to a board adds that company to the list. LinkedIn, Indeed and any board whose terms forbid it are never read.
3. Community boards, manual or semi-manual: Motionographer jobs, the ComfyUI Discord jobs channel, the aescripts community, Motion Design Slack groups, Creative Technologist listings on The Dots. These are low volume and high signal, a weekly manual sweep is fine for v1.

Seed lists live in `data/seeds/*.txt` as `category | careers url | name`, with an optional fourth field for the headquarters as `City, ST`. The nightly job runs `scraper import data/seeds` before polling and skips any company already on the list, so a list dropped in that directory is taken in on its own. Added 2026-09-05, when a count of the corpus put the yield at 0.8% and showed the binding constraint was seed coverage rather than filter quality: the scraper can only find what it is pointed at, and it was pointed at 88 companies.

A second list went in on 2026-09-05, across the western states, weighted to ones nobody would put on a top 100. Two reasons. Matt moves to Washington or Oregon in June 2027, so a company already in the west is worth knowing about early. And the top 100 is a lagging indicator: every company on it was small once, and the roles worth having are often posted before a company is famous. Its first version led with fifteen animation, VFX and title studios on the reasoning that they were closest to Matt's own discipline. That was the wrong reasoning and he said so the same day: those studios are place-based and longform, which is both principles broken at once. They were removed before anything was imported. What remains is mountain-west and coastal product companies and western brands running real in-house creative teams.

Two more lists went in with it. A remote-first list of companies that are all-remote by construction or known to pay the same wherever you sit, which is the one that serves the first principle directly, and a Midwest list, because he can work from anywhere and the point is coverage rather than a bet on a city.

Discovery's caps went up the same day, from 15 boards and 30 postings a night to 40 and 100, and moved out of the function signature into `scoring.json` so they can be tuned without a code change. The old numbers were written when the list was ten companies long.

Company boards first, aggregators second. Aggregators are where most fake-remote and underpaid listings come from, so they get the same gates but a lower prior.

## Normalization

Every listing becomes one record with these fields before any rule runs. Missing fields are `null`, never guessed.

| field | type | notes |
|---|---|---|
| `id` | string | stable hash of `source + external_id` or `source + url` |
| `source` | string | `greenhouse`, `lever`, `ashby`, `workable`, `smartrecruiters`, `recruitee`, `rss`, `manual`, or a discovery feed |
| `url` | string | canonical listing URL |
| `company` | string | as posted, then matched against `data/companies.json` by slug |
| `company_tier` | 1–4 or `null` | from `data/companies.json`; `null` if unknown |
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
- No fake-remote phrase anywhere in the body. The list is in `scoring.json` under `remote.fail_phrases`. The core ones: in-office, in office, remote for now, remote to start, initially remote, occasional office, days in the office, days per week in, commuting distance, local candidates, within N miles, relocate to. Revised 2026-09-05: "must be located in", "must reside in", "must live in" and "based in the" fail only when the place named is not the US, because "you must be based in the United States" is the standard payroll sentence on a US-remote role and was dropping genuine remote postings by the hundred. "hybrid" needs office or schedule words in the same sentence, so hybrid search and hybrid cloud stop failing the gate, and "on-site" spares a final on-site interview.
- State list is `null`, nationwide, or contains PA and at least one of WA or OR.

How `remote_claim` is read, revised 2026-09-05. A structured workplace field wins where the ATS has one. Where it does not, which is every Greenhouse board, the location text decides, and a location that names only a country or a region, "United States", "US", "North America", "Multiple Locations", is `unclear` rather than `onsite`, so the body gets to say. Before that date any location without a remote word was a hard fail before the body was read, which was 6,069 of the 9,591 logged rows on the first real digest and the whole reason Figma, Vercel and Dropbox polled a hundred postings each with none on target. A Greenhouse office named Remote makes a country location `remote` and a city location `unclear`, never a city `remote` on its own.

How the state list is read, revised the same day. Nationwide tokens are read from the location, plus the multiword ones from the body. The bare token "us" was read from the whole body before, so "join us" made every posting nationwide and the state-list and time zone rules only ever fired on bodies that never said it. State lists in the body count only inside a residency sentence, "candidates must be located in", "eligible to work from", never inside pay-transparency boilerplate, which names California, Colorado, New York and Washington on every posting and is not a residency rule.

**Fail** on any of:
- `remote_claim` is `hybrid` or `onsite`.
- Any fail phrase present.
- State list exists and does not include PA. He starts the job from Pennsylvania, so this is not negotiable for v1.
- A single named city or metro with no state list and language like "based in", "located in", "must reside".
- The location names another country and no US marker. Checked against the location only, never the body, because a US role can perfectly well mention EMEA teams. "Remote - US, Canada" passes; "Remote - LATAM" and "Electrical Design Engineer (Estonia)" do not. Added 2026-09-05 after those turned up inside the remote target set.

**Flag** (pass at half marks, reason attached) on:
- State list includes PA but neither WA nor OR. State lists change and it can be asked on the first call.
- Location reads like "Remote (San Francisco)" or "Remote - New York" with no state list and no residency language. Usually a payroll default, not a requirement. This flag is soft: it halves the remote marks and prints on the row but does not hold a tiered title in review, because once the "us" bug was fixed it fires on real matches and the point was to surface them.
- `remote_claim` is `unclear` but the body says remote and no fail phrase is present.
- Time zone requirements tighter than "US time zones". Pacific-only is fine for someone moving to the Northwest and earns the full remote marks, Eastern-only is a flag, not a fail, and it flags on a nationwide posting too.

## Gate 2: comp isn't insulting

Annualize first. Hourly times 2080. Ranges keep both ends. Gate on `salary_max`, because that's the number a negotiation can reach. Score on the midpoint, because that's the number they'll open with.

Where an ATS publishes one range per office, which is how location-adjusted pay shows up, the range with the lowest maximum is the one gated and scored, because that is the tier a remote hire outside the headquarters city is paid. Revised 2026-09-05: Greenhouse ranges were merged min-of-mins and max-of-maxes, and Ashby took the first tier, so a location-adjusted employer cleared the gate on its San Francisco number. The text parser now reads every dollar range in a description and takes the first that reads as a salary, so a home office stipend listed before the base pay no longer hides it.

**Pass**
- `salary_max` at or over the pass floor in `data/local/scoring.local.json`.
- Salary not posted, and `company_tier` is 1, 2 or 3, or `company_size` > 200.

**Flag** (passes, low comp score, reason attached)
- `salary_max` between the flag floor and the pass floor. Worth a look only at tier 1 or 2 where equity and a fast band correction are plausible. At tier 3 or 4 this is a soft drop, so score it but push it to review, never apply.

**Fail**
- `salary_max` under the flag floor.
- Hourly under the contract floor for contract or freelance work, annualized. The floor is firm, so a contract posting that lists an annual figure is held to the same number.
- Salary not posted, company not on `data/companies.json` with a tier, and size unknown or under 200. Most states with remote-hiring companies require posted ranges now, so a remote-US listing with no range is itself a signal.
- Any unpaid test project, take-home or "design exercise" described as longer than two hours, or any spec work.

Log every gate-2 fail with its reason. The Oct 5 checkpoint reviews the `unlisted_salary_unknown_company` bucket specifically, because that's the rule most likely to be throwing away good listings.

## Underpaid tells

Each match subtracts 3 from the final score. Cap the total deduction at 15. The full phrase list is in `scoring.json` under `deductions`. The intent behind each:

- "content creator", "social media videos", "short-form content", "10+ videos a week", or any per-week output quota: volume shop.
- "wear many hats", "fast-paced environment", "scrappy", "startup mentality" without a posted band: underpaid by design.
- "rockstar", "ninja", "guru", "wizard": tells you who wrote the listing.
- "junior", "jr", "mid-level", "associate", "coordinator", "intern" at the start of the title: wrong level. Revised 2026-09-05 so that Associate Creative Director, Associate Design Director, International Brand Designer and Internal Tools Designer stop being dropped by their first letters.
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
- Engineering-discipline Design Engineer titles, with the discipline before the title, RTL Design Engineer, or after it, "Data Center Design Engineer, Electrical". The after case was added 2026-09-05, when that OpenAI posting reached review at 60 because every pattern required the discipline first. A plain Design Engineer still tiers at B.
- Pure UX by title: "user experience designer", "UX/UI designer", "product designer (UX". These were already listed as body phrases, but disqualifiers match phrases against the body only, so a posting titled User Experience Designer was never dropped. It mattered little while no product title could tier, and it matters now that one can.
- Longform animation in any form, staff or freelance. Fixed-fee bids for a full animated piece, and as of 2026-09-05 also feature film, animated feature, episodic, theatrical, television or broadcast series work, plus the film-pipeline titles that only exist to serve it: character animator, storyboard artist, layout artist, compositor, roto, matchmove. This is one of the two guiding principles and it is absolute.
- Relocation required or "relocation assistance provided" as a substitute for remote.
- Travel over 10%.
- Contract-to-hire with a conversion salary below the floor, or no conversion salary stated.
- Postings older than 30 days with no repost. `posted_at` older than 30 days and `last_seen` more than 7 days ago.
- Roles whose primary requirement is a discipline he doesn't have and can't credibly bridge: pure UX/UI product design, pure brand strategy, pure ML research, pure sound design. Research scientist, ML researcher and machine learning engineer are title patterns as of 2026-09-05, not body phrases, because every Design Engineer posting at an AI company says it works alongside one.
- Film-pipeline titles, added 2026-09-05: fx, vfx, cfx, lighting, rigging, creature, groom, previs, look dev, environment and texture artists, TDs, supervisors and leads, CG supervisor, stop motion. Senior Animator and Creature FX Technical Director at a commercials shop were reaching apply.

**Flag, don't drop**
- Unreal or Unity as the primary tool. Technical Artist listings often want a game engine. The eye and the pipeline thinking transfer, the engine doesn't, but it's worth Matt's call. Revised 2026-09-05: the phrases are unreal, ue4, ue5, unity engine, in unity, hlsl. "shader" and "glsl" left the list because they are curriculum web-motion vocabulary and were holding a Design Engineer in review for the words the search rewards, and bare "unity" matched "team unity". The flag still holds a tier B title, tier A overrides as before.
- A flag holds a posting in review so Matt decides, **except where the title is tier A**. Added 2026-09-05, after Creative Technologist at Luma, the stated bullseye, scored 70 and sat in review because the body mentions Unity. A tier A title is the thing being searched for, so the flag prints on the row and the posting still reaches the pile the letter generator reads.
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
- `3d`: cinema 4d, c4d, redshift, octane, houdini, blender, maya, 3d modeling, 3d modelling, 3d animation, 3d artist, 3d generalist, hard surface, retopology, uv mapping, look dev, lookdev, texturing, lighting and rendering, render farm
- `motion`: after effects, motion design, motion designer, motion graphics, animation, compositing, premiere, brand motion, kinetic type, logo animation
- `generative`: diffusion model, latent diffusion, diffusion transformer, comfyui, stable diffusion, flux.1, flux model, text-to-video, text to video, image-to-video, image to video, img2vid, ai video, ai image, generative video, generative image, generative art, lora, controlnet, upscal, inpaint, kling, veo, sora, hailuo, minimax video, ltx
- `software`: python, javascript, typescript, extendscript, cep, plugin, panel, scripting, automation, api, rest api, restful, node, tooling, agentic, llm, local models, llama.cpp, ollama, cuda, pytorch
- `pipeline`: pipeline, asset management, mam, dam, metadata, taxonomy, naming convention, iconik, frame.io, workflow, render farm, versioning, asana, shotgrid, ftrack

  The `generative` terms were bounded again on 2026-09-05, after the Economist posting at OpenAI kept its generative leg through the first cut. Bare `diffusion` matched the diffusion of innovation, bare `flux` matched a market in flux, and bare `minimax` matched minimax regret. Each is now written in its product sense, `diffusion model` and `latent diffusion` and `diffusion transformer`, `flux.1` and Flux checkpoints and LoRAs, `hailuo` and MiniMax video. Three words that name both an economics idea and a model family, which is exactly the shape of false positive the first cut was for.
- `product`: figma prototyp, figma, design system, design systems, component library, interaction design, design tokens, motion system, motion systems, product animation, ui animation, interface animation, animation system, motion guidelines, micro-interaction, microinteraction, plus every term in the curriculum's product-motion vocabulary as of 2026-09-05, storybook, prototyping, protopie, origami, framer, spline.design, rive, lottie, bodymovin, smart animate, variable fonts, motion principles, motion language, animation principles, motion tokens, prototype, design handoff. Half of that vocabulary sat in no leg before, so a Product Designer whose body named only Lottie and Rive could not satisfy tier B's leg gate, and the funnel selected generic Figma roles over product-motion roles and then reported that selection back as the study list. It scores as intersection, and deliberately does not satisfy the tier B leg gate on its own for a title that is not a design title.

**Title tiers**
- Tier A (15): creative technologist, technical artist, design technologist (zero occurrences in 6,425 postings as of 2026-09-05, kept here because it costs nothing and would be a bullseye, removed from the discovery term lists where it only spent match budget), creative engineer, motion design engineer, creative developer, generative ai designer, generative ai artist, generative artist, ai creative lead, ai creative director, creative ai engineer, creative ai designer, creative ai artist, creative ai lead, creative ai director, pipeline td, pipeline technical director, motion technologist, technical director, motion systems, motion system designer, product motion, design systems engineer. Revised 2026-09-05: technical director and pipeline td need a generative, software, pipeline or product leg, because Creature FX Technical Director at a VFX house tiered A and overrode every flag, and bare "creative ai" put Creative AI Product Manager in apply at 80.
- Tier B (10): motion designer, motion graphics designer, 3d motion designer, 3d artist, 3d generalist, art director, design engineer, motion lead, head of motion, animation director, **product designer, brand designer, visual designer**, and as of 2026-09-05 interaction designer, ux engineer, prototyper, design systems designer, motion design lead, motion director, product motion designer, when the body also hits the `generative`, `software`, `pipeline` or `product` leg. The product-motion titles were untiered before, so Interaction Designer with a Figma and design-systems body scored 70 and could never reach apply.

  Product and brand titles added 2026-09-05. Product Designer is 130 of the corpus against Motion Designer's 25, it is where the remote volume and the pay are, and roughly 29 of the 59 remote target roles are at AI video and image companies where those titles are how the work is advertised. Luma posted Creative Technologist twice and also Visual Designer Product. The leg gate is what reconciles that with the thesis: `product` alone never earns a tier, so a Product Designer role tiers at an AI video company that wants generative or pipeline work and does not tier at a bank. Pure UX is still dropped outright.
- Tier C (5): motion designer, motion graphics designer, motion graphics artist, 3d artist, animator, 3d generalist, when the body hits none of the tier B legs. Tier C never reaches apply as of 2026-09-05, review at most: it is the work being left, and with posted comp at a tier 2 company a Senior Animator at a commercials shop was reaching apply at 66.

## Piles

- **Apply**: score ≥ 65 **and a tier A or B title**. Added 2026-09-05: the apply pile is what the letter generator reads, and a posting whose title does not fit is not one Matt can write a credible letter for, whatever the body scores. It is how an Economist and a PCB Layout Engineer reached apply on generic body language. They still reach review. Goes to the cover letter generator with the listing record, the tier and the proof-point lead for that tier (see `proof-points.json` when it exists, until then tier 1 leads with the ComfyUI pipeline, tier 2 with AE Llama, tier 3 with the tooling record, tier 4 with franchise ownership).
- **Review**: 45–64, plus anything with a flag regardless of score, unless the title is tier A. Matt skims on Mondays.
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

- Sep 2 to Sep 6: collect only, compressed from a month on 2026-09-02 because Matt does not expect to still be in his current job in two. Use the first digests to check the gates aren't throwing away obvious fits. A posting scoring 80 or better is named in the digest anyway; it will not wait.
- Sep 6: first apply pile, the very first digest.
- Oct 5 checkpoint: if tier 1 and 2 response rate is under 10% after 20 applications, the problem is the materials, not the rules. If the apply pile is thin, loosen `unlisted_salary_unknown_company` first, then title tier B, in that order. Never loosen gate 1.

## Open questions for Matt

- Any companies where a state-list flag should be ignored because he'd move early for them?

Answered 2026-09-02: Pacific-only outscores US-wide, and $85/hour is a firm floor for contract work.
