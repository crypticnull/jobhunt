# jobhunt

![ci](https://github.com/crypticnull/jobhunt/actions/workflows/ci.yml/badge.svg)

A senior motion designer who ships software is going to market as exactly
that, and this repo is both the toolkit for the search and a public record
of how he works. Three things share one data spine: a portfolio site, a
poller against public ATS endpoints, and a cover letter generator with a
voice lint that refuses anything that reads as machine-written. Everything
runs locally on standard-library Python plus one pinned Astro site, and the
private half of the search never touches git.

## The ten minute tour

**Minutes 0 to 2, the thesis and the history.** Read the paragraph above,
then `git log --oneline`. Package-prefixed commits, one working change
each, no squashing. The graph is evenings and weekends and it says so.

**Minutes 2 to 4, two decisions.** [ADR-0002](docs/decisions/0002-privacy-split.md)
is the privacy split: a public repo whose intended readers include hiring
managers at target companies, so the target list, the postings database,
the letters and the salary figures live in `data/local/` and a pre-commit
guard refuses them. [ADR-0004](docs/decisions/0004-python-stdlib-only.md)
is stdlib-only Python, because this runs unattended for months on one
workstation and every dependency is something that rots. The rest are in
[docs/decisions](docs/decisions/), 25 lines each, written the day they
were made.

**Minutes 4 to 6, run it.**

```
make demo
```

Polls the example companies from recorded fixtures into a throwaway
store, scores and digests them, writes a brief for the top posting,
assembles a draft from the letter blocks, lints it and files it. Offline,
under a minute, no credentials. What the README claims, that runs.

**Minutes 6 to 8, the tests.**

```
make hooks && make test && make validate && make lint
```

133 tests, all offline against fixtures, the JSON records validated
against their schemas, and every doc and the site source checked by the
voice lint. CI runs the same plus the site build with Lighthouse budgets:
CLS 0, performance 90 and accessibility 95 or better, three runs, median.

**Minutes 8 to 10, the site.** `cd site && npm install && npm run dev`
until the domain lands. The order of the page is the strategy: the
intersection sentence, then what he builds, then the motion work as proof.

## Layout

| Path | What |
| --- | --- |
| [`PLAN.md`](PLAN.md) | the execution plan, twelve milestones, every decision with its reasoning |
| [`data/`](data/) | the shared spine: schemas, project and pipeline and proof records, scoring and voice config; `data/local/` is private |
| [`scraper/`](scraper/) | ATS detection, seven adapters, the SQLite store, scoring, the weekly digest, discovery and backups |
| [`letters/`](letters/) | the block library, the brief, the lint-gated save, the voice lint |
| [`pipeline/`](pipeline/) | asset intake from named drops, media probing, record validation |
| [`site/`](site/) | Astro 7, static, reading `/data` through typed collections |
| [`docs/`](docs/) | decisions, the session log, the weekly process, the naming spec, this standard |
| [`tools/`](tools/) | the schema drift check and the demo |

## Running it for real

`docs/process.md` is the schedule. Add companies with `python -m scraper
add <careers-url> --category ...`, register the nightly poll and Sunday
digest with `scripts/install-schedule.ps1`, and the loop runs on schedule
instead of willpower.

## Limits, honestly

The cloud sandbox that built most of this cannot reach the ATS hosts, so
the live endpoint smoke test runs on the workstation. Workable's widget
API is unofficial and the likeliest adapter to need a fixture refresh.
The first Lighthouse run on a cold CI runner scored 0.82 once; three runs
and a median fixed the measurement, not the budget. The portfolio's video
and stills arrive on their own schedule, and until they do the site
carries placeholders and says so.
