# The weekly loop

The scraper and the letters exist so the search runs on schedule instead of
willpower. This is the schedule.

## Every night, unattended

`python -m scraper poll` at 02:30, `python -m scraper backup --to <off-disk
dir>` after it. `scripts/install-schedule.ps1` registers both in Task
Scheduler along with the Sunday digest. A missed night costs nothing;
postings are closed and reopened by what the next poll sees.

## Sunday, unattended

`python -m scraper digest` writes `data/local/digests/<week>.md`.

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

The first month is collect-only. Until 2026-10-05 the digest carries a
banner and the piles are read for one reason: to check that the gates are
not throwing away obvious fits. The first apply pile is the digest of
2026-10-05. The checkpoint is 2026-11-16, when the drop counts and the
response rate decide whether the unlisted-salary rule or the title tiers
loosen, in that order. The remote gate never loosens.

## Any evening, one application

1. `python -m letters brief <id>`, read it, choose the opening and the close.
2. Draft the letter from the brief, in a Claude Code session or by hand.
3. `python -m letters save <id> draft.md`. If it refuses, fix the draft; the
   lint is the last word on the voice.
4. Send it yourself. Nothing here sends anything.
5. `python -m scraper mark <id> applied --letter <saved path>`.

New companies enter the list through `python -m scraper import <file>`,
one per line as `category | careers url | name`, or one at a time with
`python -m scraper add <careers url> --category <category>`. The tier
follows the category, so nothing else needs setting.

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
