# 0008: The search protocol is the scoring engine

Date: 2026-09-02
Status: accepted

## Context

Version one of `data/scoring.json` was a ranking: every rule added a
signed number, nothing was dropped, and a weekly digest sorted the open
postings into strong, borderline and comp not posted. Matt had meanwhile
written a search protocol by hand, with two hard gates, a hundred-point
score, apply and review piles, a weekly cap, a collect-only month and a
checkpoint. Two documents that describe the same search drift apart.

## Decision

The protocol replaces the ranking. `docs/search-protocol.md` is the copy
Matt reads, `data/scoring.json` is the copy the scraper runs, and a
change to one is a change to the other, committed together. A posting
that fails a gate is a row with a pile of `logged` and a reason, never a
deletion, so the drop counts are in every digest and the checkpoint can
see what the gates threw away. The comp floor and bands stay in
`data/local/scoring.local.json`, null in the committed file. The remote
gate never loosens.

## Tradeoff accepted

Gates drop postings the old ranking would have surfaced. The collect-only
month and the drop counts exist to catch a gate that is wrong.
