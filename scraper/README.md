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
python -m scraper import FILE [--priority 1|2|3] [--manual]   # many companies from a text file
python -m scraper check              # probe every endpoint, exit 1 if any is dead
python -m scraper stale --days 60    # companies nobody has looked at lately
python -m scraper poll               # read the feeds, add what they give away, fetch every board, score on the way in
python -m scraper digest [--stdout]  # this week's digest to data/digests/<week>.md, pushed on Sundays
python -m scraper score              # rescore every open posting after tuning scoring.json
python -m scraper mark ID STATE      # new | reviewed | applied | screen | loop | offer | rejected | skipped
python -m scraper stats [--markdown --since 2026-09-01]   # the monthly snapshot block
python -m scraper add-posting SRC --company SLUG --title T  # a referral, from a URL or a file
python -m scraper discover           # what the feeds are surfacing right now, nothing written
python -m scraper backup --to DIR    # postings.db off the disk, newest fourteen kept
python -m scraper export --to DIR    # status history as JSON, one file per month
python -m scraper fixture KIND BOARD # refresh a test fixture from the live endpoint
```

`docs/process.md` is the schedule these run on. On Windows, `setup.cmd`
at the repo root does the whole install in one double-click and writes
what happened to `setup.log`.

## Discovery

The list grows on its own. Every night before the boards are polled, the
poll reads six remote job feeds (Remotive, We Work Remotely, Himalayas,
Jobicy, Arbeitnow, RemoteOK) and the month's Hacker News "Who is hiring"
thread, and keeps every remote posting that names something only a
creative-technical role names. That list is `discovery.require_any` in
the ruleset, and it is deliberately tighter than the scoring legs: `api`,
`automation` and `rendering` are fair signals on a company already on the
list and match every backend and QA job in an open feed. Sales, QA,
marketing and support titles are excluded outright, and a posting with no
usable company name is dropped rather than guessed at.
A posting whose links give away a Greenhouse, Lever, Ashby, Workable,
SmartRecruiters or Recruitee board hands over the company's whole board,
and where the links give nothing away the job page itself is fetched once,
up to twelve a night, because the feeds link to themselves and the apply
button is where the real board leaks out. A board found this way
so the company is added to the list as pollable means everything that company
posts is watched from then on. A posting with no board behind it is stored as
a posting in its own right, under a hand-check company record, so nothing
relevant is lost for lack of an ATS. Discovered companies carry the
category `discovered` and no tier until Matt gives them one, which means
an unlisted salary fails the comp gate for them and a listed one competes
on merit. Caps of fifteen new boards and thirty feed postings a night
keep one wild evening from doubling the list. One dead feed never stops
the others; the digest's source health footer names it.

The hand-written list is still welcome, through `import` or `add`, and a
tier on a record is what promotes a discovered company to a target.

`import` takes a text file with one company per line, `category | careers
url | name`, and runs `add` on each, so a first list of eighty companies
is one command. Anything without a detectable ATS is reported at the end
rather than written, unless `--manual` says to keep it for hand checks.

`add` works out the ATS from the careers URL, or from the board links
embedded in the page, and confirms the guess against the live endpoint
before writing. `--kind manual` records a company that has to be checked by
hand. The list lives at `data/companies.json` in the repo, public, so it
can be read and edited from anywhere; contacts and notes on a company sit
in `data/local/companies.notes.json`, private, merged in on load. The
nightly task pushes the list after discovery grows it. `--companies` and
`--db` point anywhere else.

## Scoring

The search protocol lives twice: `docs/search-protocol.md` is the version
Matt reads and `data/scoring.json` is the version the scraper runs, and a
change to one is a change to the other. `score.py` applies it in order.

1. Two hard gates. Remote has to be real, so a hybrid claim, a fake-remote
   phrase, or a state list that leaves out Pennsylvania fails the posting.
   Comp has to clear a floor, so a posted max under it fails and an
   unlisted salary passes only at a tier 1 to 3 company or one with more
   than two hundred people.
2. Disqualifiers. Editor and junior titles, relocation, heavy travel, fixed
   fee work, pure UX, research roles, and anything stale.
3. A score out of 100. Remote 25 for Pacific hours or 22 US-wide, comp 20, the intersection legs 20 at five
   per leg (3D, motion, generative, software, pipeline), the title tier
   15, the company tier 10, freshness 5, a named human 5, and up to 15
   off for underpaid tells like fast-paced or rockstar.
4. Piles. Seventy and up is apply, fifty to sixty-nine or anything flagged
   is review, the rest is logged with a reason. Engine and frontend
   language flags rather than drops, since Matt decides those.

A failed gate is a row with a pile of `logged` and a `drop_reason`, never a
deletion, so the digest counts drops by reason and the checkpoint can see
what the gates threw away. Every number that describes the comp band is
null in the committed file and comes from `data/local/scoring.local.json`,
merged at load. Without that file, posted comp is flagged rather than
scored. Every posting carries its per-rule breakdown, the ruleset version
and the proof story to lead with, so history can be rescored after tuning.

## The digest

The Monday read. New listings by source, the apply pile sorted by company
tier then score and capped at twelve a week, the review pile with its
flags, drops counted by reason, and a footer naming any source that
errored or returned nothing twice running. Postings with a terminal
status, or already surfaced and unchanged, stay out. Until the collect-only
date in `tuning` the digest carries a banner and nothing is applied to;
the piles are read to check the gates. On Windows,
`scripts/install-schedule.ps1` registers the nightly poll and the digest in
Task Scheduler.

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
| `score.py` | the protocol: gates, disqualifiers, score, piles, pure functions over a posting row, its company record and `scoring.json` |
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
