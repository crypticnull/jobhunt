# 0010: The company list is public

Date: 2026-09-02
Status: accepted

## Context

ADR-0002 put the company list in `data/local/`, private. Matt wants the
search run from chat, hands off, which means the list has to be readable
and editable from anywhere, and the nightly discovery step grows it on
his machine, so the two copies would drift. A list of company names,
boards and tiers is also not much of a secret: the boards are public and
the tiers say which kind of company he rates, which his site says too.

## Decision

`data/companies.json` is committed. The nightly task pushes it after
discovery grows it, and edits made from chat merge into it the same way.
Contacts and notes on a company are the private half and live in
`data/local/companies.notes.json`, keyed by slug, merged in on load and
split out on save; the public file never carries them, and the save path
enforces that rather than trusting anyone to remember. Postings, digests,
letters and the brief stay private as before.

## Tradeoff accepted

Anyone can read where he is looking. Matt decided that is fine.
