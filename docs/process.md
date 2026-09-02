# The weekly loop

The scraper and the letters exist so the search runs on schedule instead of
willpower. This is the schedule.

## Once, five minutes

Double-click `setup.cmd` in the repo folder. It checks that git knows a
name and email and that Python is on the PATH, pulls the latest, seeds
the company list from `assets/companies.txt` if one is there, registers
the two scheduled tasks, runs the first poll, and pushes the list. Every
step says pass or fail and the run continues either way, and the whole
record lands in `setup.log`, so a closed window loses nothing. Running it
again is safe. Nothing else is ever typed; the nightly task pulls updates
before it runs.

## Every night, unattended

The time is a setting, not a rule. `setup.cmd 03:00` or
`.\scripts\install-schedule.ps1 -NightlyAt 03:00` moves it.

`scripts/nightly.cmd` at 04:00, registered to catch up rather than skip if
the machine was off or asleep at the time, and at the lowest scheduler
priority so an overnight render keeps the CPU: pull main, then `python -m
scraper poll`,
which reads the discovery feeds, adds the boards they give away, polls
every board, and scores everything on the way in, then push the company
list if it grew, then a backup to the directory in
`data/local/backup-dir.txt`. A missed night costs nothing;
postings are closed and reopened by what the next poll sees.

## Sunday, unattended

`scripts/weekly.cmd` at 07:00: pull main, then `python -m scraper
digest`, which writes `data/digests/<week>.md`, then push it, so the
digest can be read and talked about from chat.

## Monday, fifteen minutes minimum

1. Read the digest. The apply pile first, then review, then the drop
   counts by reason.
2. Mark what you are not doing so it never comes back:
   `python -m scraper mark <id> skipped`.
3. Pick what you will write to this week. `python -m scraper mark <id>
   reviewed`. The apply pile is already capped at twelve; three is a good
   week.

That is the whole week when work is bad. The digest still arrives, the
statuses still move, nothing rots.

The collect-only window is four days, not a month. It was a month, and it
was compressed on 2026-09-02 because Matt does not expect to still be in
his current job in two. The first digest, Sunday 2026-09-06, already
carries an apply pile. Until then the digest carries a banner and the
piles are read to check that the gates are not throwing away obvious
fits, and any posting scoring 85 or better is named in the digest anyway,
because a job that good is gone in a fortnight. The checkpoint is
2026-10-05, when the drop counts and the response rate decide whether the
unlisted-salary rule or the title tiers loosen, in that order. The remote
gate never loosens.

## Any evening, one application

1. `python -m letters brief <id>`, read it, choose the opening and the close.
2. Draft the letter from the brief, in a Claude Code session or by hand.
3. `python -m letters save <id> draft.md`. If it refuses, fix the draft; the
   lint is the last word on the voice.
4. Send it yourself. Nothing here sends anything.
5. `python -m scraper mark <id> applied --letter <saved path>`.

New companies mostly enter the list on their own, through the discovery
feeds the nightly poll reads. A hand-picked one goes in through
`python -m scraper import <file>`, one per line as `category | careers
url | name`, or `python -m scraper add <careers url> --category
<category>`. The tier follows the category. A discovered company has no
tier until it is given a category; the digest lists the ones found each
week.

A referral or a company without a feed enters the same loop through
`python -m scraper add-posting <url-or-file> --company <slug> --title "..."`.

## First of the month, ten minutes

1. `python -m scraper stats --markdown --since <first of last month>` and
   paste the block into the month's log entry with `scripts/log.sh`. Real
   numbers for the case study, seen, surfaced, applied, responses, with
   the companies behind them staying private.
2. `python -m scraper export --to <off-disk dir>` for the status history.
3. `python -m scraper stale --days 60` and review or drop what it lists.
4. `python -m scraper discover` for companies the feeds keep surfacing.

## Every quarter, an hour

Read the last three months of digests against what actually got a
response. Tune `data/scoring.json` where the digest was wrong in the same
direction twice, change `docs/search-protocol.md` to match, commit both
with the reason, and `python -m scraper score` to rescore history under
the new ruleset. The `ruleset_version` on every row is what makes that
honest.

## When an endpoint drifts

`python -m scraper check` shows it dead, or a poll starts logging parse
errors, or a digest footer names a source twice running. Then:

1. `python -m scraper fixture <kind> <board>` fetches the live payload
   and writes a trimmed copy over the adapter's test fixture.
2. `make test` shows exactly which fields moved. Fix the adapter until it
   passes, commit the fixture and the fix together. The diff is the
   record of what the platform changed.

Workable is the one flagged as likeliest to drift. RSS feeds are the
fallback for any company whose ATS stops answering.
