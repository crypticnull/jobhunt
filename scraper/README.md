# scraper

A company-list-driven poller against public ATS endpoints. Python 3.12,
standard library only (ADR-0004). It never scrapes job boards; it asks
Greenhouse, Lever, Ashby, Workable, SmartRecruiters and Recruitee for the
JSON they publish for each company on the target list, reads a careers RSS
or Atom feed where that is all a company offers, and the target list is
the asset.

## Commands

```
python -m scraper add URL --category ai-video [--name N] [--priority 1|2|3] [--lead-proof ID]
python -m scraper check              # probe every endpoint, exit 1 if any is dead
python -m scraper stale --days 60    # companies nobody has looked at lately
python -m scraper poll               # fetch every pollable company, score on the way in
python -m scraper digest [--stdout]  # this week's digest to data/local/digests/<week>.md
python -m scraper score              # rescore every open posting after tuning scoring.json
python -m scraper mark ID STATE      # new | interested | applied | rejected | ignored | interview | offer
python -m scraper stats [--markdown --since 2026-09-01]   # the monthly snapshot block
python -m scraper add-posting SRC --company SLUG --title T  # a referral, from a URL or a file
python -m scraper discover           # companies the discovery feeds surface, never written
python -m scraper backup --to DIR    # postings.db off the disk, newest fourteen kept
python -m scraper export --to DIR    # status history as JSON, one file per month
python -m scraper fixture KIND BOARD # refresh a test fixture from the live endpoint
```

`docs/process.md` is the schedule these run on.

`add` works out the ATS from the careers URL, or from the board links
embedded in the page, and confirms the guess against the live endpoint
before writing. `--kind manual` records a company that has to be checked by
hand. The list lives at `data/local/companies.json` and is private;
`--companies` and `--db` point anywhere else.

## Scoring

The search protocol is `data/scoring.json`: weights, term lists and
thresholds, committed and diffable. The comp band is private and lives in
`data/local/scoring.local.json` as `{"comp_band": {"min": …, "max": …,
"currency": "USD"}}`; without it, comp is flagged rather than scored.
Every posting carries its per-rule breakdown and the ruleset version, so
the digest can show its reasoning and history can be rescored after tuning.
Scoring ranks. It never drops.

## The digest

Three lanes: strong, borderline, and comp not posted, each entry with the
rules that put it there and the id to `mark` it with. Postings with a
terminal status, or already surfaced and unchanged, stay out. The footer
names any source that errored or returned nothing twice running. On
Windows, `scripts/install-schedule.ps1` registers the nightly poll and the
Sunday digest in Task Scheduler.

## Shape

| File | Job |
| --- | --- |
| `http.py` | the only network access, stubbed in tests |
| `adapters/` | one module per source: `endpoint(board)` and `parse(payload)` to normalized postings, plus `fetch()` where a source needs more than one call; detection and probing in `__init__` |
| `posting.py` | the normalized posting, mirrored by `data/schema/posting.schema.json` |
| `companies.py` | the target list: load, save, add, check, stale |
| `store.py` | the only writer of postings.db, forward-only migrations, status as a log |
| `poll.py` | one poll, every company isolated and logged, comp filled from text when the ATS gave none |
| `salary.py` | the regex that pulls a range out of description text |
| `score.py` | the rules, pure functions over a posting row and `scoring.json` |
| `digest.py` | the weekly markdown |
| `manual.py` | a posting from a URL or a file |
| `discover.py` | Remotive and We Work Remotely as suggestion feeds |
| `maintain.py` | backup, export, fixture refresh |

Deduplication: the fingerprint is `source:id` when the ATS gives an id, else
a hash of company plus normalized title. A posting that vanishes from a
successful poll is closed, never deleted, and reopens if it comes back.
SmartRecruiters needs one detail call per posting for the description,
capped at sixty; a failed detail leaves the description empty rather than
failing the company. Workable's widget API is unofficial and the likeliest
to drift, which is what `fixture` is for.

## Tests

```
make test
```

Everything runs offline against recorded shapes in `tests/fixtures`. The
live smoke test of the endpoint patterns runs on the workstation, since
the cloud sandbox cannot reach the ATS hosts.
