# Asset intake: what the portfolio needs from the archives

This is the brief for a scanning session. Point an agent at the drives, hand it
this file, and it should come back with a manifest of candidate files. It is
written for an agent that can read directories but does not know the work.

## The one rule

**Report, don't move.** Do not copy, rename, convert or reorganise anything.
The archives are the master copies and some of these projects are hundreds of
gigabytes. Produce a manifest, Matt reviews it, and only then does anything get
pulled across.

A scan that returns 400 rows of honest candidates is a success. A scan that
returns 12 rows because it guessed at relevance is a failure, and so is one
that copies 80 GB of renders into a staging folder.

## What the manifest looks like

One TSV, one row per candidate file, written to `data/local/intake/<scan>.tsv`
which is gitignored:

```
path	bytes	modified	project	year	deliverable	stage	confidence	note
```

- `path` absolute, exactly as found
- `project` the slug from the table below, or `unknown`
- `deliverable` what the file is a piece of: `logo-loop`, `key-art`, `opener`,
  `animation-package`, `title-card`, `lower-thirds`. Guess from the filename
  and the folder, and say `unknown` when it is not obvious
- `stage` one of `final`, `hero`, `poster`, `still`, `storyboard`, `styleframe`,
  `wip`, `breakdown`, `source`, `dev`
- `confidence` `high`, `medium` or `low`. Low is fine and useful. A row that is
  honestly marked low costs nothing; a wrong row marked high costs a review
- `note` anything that would help a human decide, especially "there are 40 more
  files like this in the same folder"

Where a folder holds an obvious sequence, one row for the folder with a count
in the note beats 300 rows.

## What counts as a find

Ranked. The first three are what makes a case study exist at all; the rest is
what makes it worth reading.

1. **Final** the delivered film. Prefer the highest-quality export that exists,
   ProRes or master over the compressed delivery copy, because the site
   generates its own renditions. One per deliverable.
2. **Hero** a single still that represents the project. Key art, a title frame,
   the best frame. 1920 wide or better, and larger is better.
3. **Stills** three to eight frames that show range rather than repeat the hero.
4. **Storyboards** the actual boards. Rough pencil, marker, thumbnails, anything.
   These are usually PDFs, PSDs or a folder of numbered JPGs.
5. **Styleframes** look development frames. **Include the rejected directions.**
   The versions that lost are the most interesting material in the archive and
   they are the thing almost no portfolio shows.
6. **WIP and breakdown** render passes, wireframes, AOV contact sheets, before
   and after grades, turntables, UV layouts, retopo screenshots.
7. **Dev** the machinery. Expression snippets, scripts, C4D scene tree grabs,
   Redshift or Octane settings, Houdini node graphs, rig screenshots, naming
   spreadsheets, anything that shows how the thing was actually made rather
   than what it looked like. Mark it `dev` and note what it is. This is the
   material that makes a motion project read as engineering, and it is the
   category most likely to be skipped, so err toward including it.
8. **Source** project files: `.aep`, `.c4d`, `.hip`, `.prproj`, `.psd`, `.ai`.
   **Locate them and record the path. Never copy them.** They are the fallback
   when a still needs re-exporting, and knowing where they are is the whole
   value.

## What to skip

- Anything under a folder named for a partnership, co-brand or a third party's
  name. Internal POWER work is cleared; partnership material is not, and
  nothing from it goes in the manifest.
- Renders, caches, proxies, previews, autosaves, `.aep` backups, `Adobe Premiere
  Pro Preview Files`, `_cache`, `proxy`, `autosave`, `Backup`.
- Anything with `wip_old`, `DO NOT USE`, `deprecated`, `archive_old` in the path,
  unless it is a styleframe, where rejected directions are wanted.
- Footage rushes and stock. The site shows delivered work and process, not
  source plates.
- Audio, unless it is a final mix belonging to a specific deliverable.

## Naming, for later

The manifest does not need to rename anything. This is here so the `deliverable`
and `stage` columns are filled in with the right vocabulary, and so Matt can see
where a row is heading. `docs/naming.md` is the authority.

```
{project}_{year}_{deliverable}_{stage}_v{NN}.{ext}

quest_2025_logo-loop_final_v03.mp4
quest_2025_key-art_hero_v01.png
nitro-create_2026_logo-loop_storyboard_v01.jpg
summit_2025_opener_styleframe_v04.png
```

Once a manifest is approved, the accepted files are copied into one flat folder
under those names and `python -m pipeline.ingest <folder>` writes them into the
records. Nothing is edited by hand.

## The projects

`status` is what the repository holds today. "record only" means the frontmatter
exists and every asset is a placeholder.

| Project | Slug | Year | Client | Status | Where to look |
| --- | --- | --- | --- | --- | --- |
| Quest | `quest-2024` | 2024 | POWER | nothing | first Quest cycle. Wanted so 2025 has a cycle 1 to sit against, even poster-only |
| Quest | `quest-2025` | 2025 | POWER | record only | key art, animation package, logo loop |
| Nitro Create | `nitro-create-2025` | 2025 | POWER | nothing | first Nitro Create cycle |
| Nitro Create | `nitro-create-2026` | 2026 | POWER | record only | logo loop, identity |
| Summit | `summit-2025` | 2025 | POWER | record only | logo loop, branding expansion. **Also flag anything showing dates and Asana task titles**, see below |
| Power Awards Gala | `pag-2026` | 2026 | POWER | nothing | most recent, may still be in progress |
| Banfield Pet Hospital | `banfield-<year>` | ? | Banfield | nothing | agency era. **Need the year and which studio, Quango or Think Joule** |
| LiveRamp | `liveramp-<year>` | ? | LiveRamp | nothing | agency era, same question |

### Others already mentioned, worth scanning for while the drives are open

You asked what you were blanking on. These have come up and none has a record:

| Project | Likely slug | Year | Note |
| --- | --- | --- | --- |
| Power Camp | `power-camp-<year>` | ? | POWER event |
| HQ Soiree | `hq-soiree-2025` | 2025 | POWER event |
| HVHZ door presentation assets | `hvhz-doors-<year>` | ? | full 3D set modelled, lit, rendered and delivered inside one day. That turnaround is the story |
| Bill of Rights | `bill-of-rights-2024` | 2024 | appears as an example in `docs/naming.md`, so confirm whether it is real work or a placeholder |
| Voidfall Survivors | `game-2026` | 2026 | personal. Has a proof record, no project record. Needs title screen, sprite sheets, the eight-angle sets |
| Ford, LinkedIn, Oportun explainers | `guidespark-<client>-2019` | 2019 | GuideSpark era |
| Portland building brand suite | `<building>-<year>` | 2016–2019 | Think Joule. Still in use, which is worth saying |
| School mascot | `<school>-mascot-<year>` | 2016–2019 | Think Joule. Also still in use |
| Quango client work | various | 2020–2022 | the $350k of delivered value. Worth a sweep for the two or three best |

### Summit 2025, one extra thing

Collamore's site shows this work without crediting you. Nothing about that goes
on the site beyond a credits line. But while the drives are open, note the file
dates and any Asana task titles that appear in screenshots or exports, because
provenance is easiest to collect now and impossible to reconstruct later. Put
them in `data/local/`, which never reaches git.

## What no scan can find

Every project needs these from Matt, and files cannot supply them. One short
block per project is enough:

- **The brief in one sentence.** What was asked for.
- **The constraint.** What made it hard. A deadline, a rebrand mid-flight, a
  render budget, a stakeholder who changed their mind at the styleframe stage.
- **Dates.** Kickoff and delivery, so turnaround is computed rather than
  remembered. Only stated on the site where it is genuinely impressive.
- **Role.** What you actually did, as distinct from what the team did.
- **Credits.** Who else worked on it and what they did. You said collaborators
  get named, case by case, so this is per project and your call each time.
- **Tools.** The real list, including the ones that are unglamorous.
- **The build.** For each project, the one thing you made or automated to get it
  done. An expression, a script, a naming system, a render setup, a template.
  Every motion study on this site carries a Build chapter, and this is it. If
  the honest answer for a project is "nothing, it was hand work", that is a
  fine answer and the chapter says so.

## Priority

If the scan has to be bounded, do it in this order. Three complete projects
beat eight thin ones.

1. Quest 2025 and Quest 2024, because the through-line needs two cycles
2. Summit 2025, because of the provenance question
3. Nitro Create 2026 and 2025
4. PAG 2026
5. Banfield and LiveRamp, which widen the client list beyond one employer
6. Everything else
