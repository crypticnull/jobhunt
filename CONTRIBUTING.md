# Contributing

One person works here, but the repo is read by strangers, so the rules are
written down and followed.

## Commits

- Package-prefixed subjects: `scraper:`, `letters:`, `site:`, `pipeline:`,
  `tools:`, `data:`, `docs:`, and `repo:` for cross-cutting root files.
- Imperative subject, body says why when the diff cannot.
- Cite the ADR number when a commit executes a decision.
- One working change per commit. No squashing; the graph is part of the
  record.
- Milestones get tags: `v0.1-scraper-live`, `v0.2-first-digest`, and so on.

## Decisions

Framework, dependency, paid service or architecture calls get an ADR in
`docs/decisions` the day they are made, 25 lines maximum. Start one with
`scripts/new-adr.sh "short title"`. See ADR-0001.

## Session log

Every work session ends with one entry in `docs/log`, 15 lines maximum,
prefilled by `scripts/log.sh` from the day's commits. Dead ends stay in.

## Setup

After cloning: `make hooks` installs the pre-commit guard that refuses
`.db` files and `data/local/` paths, then `make test`. Python 3.12,
standard library only (ADR-0004). On Windows, run the scripts from Git
Bash.

## Prose

Repo prose avoids em dashes and corporate vocabulary. The voice lint
(milestone 5) will enforce this; until then, self-police.
