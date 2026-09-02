# 0009: Discovery grows the list

Date: 2026-09-02
Status: accepted

## Context

The scraper polls company boards, and the company list was hand-written.
Matt called that slow, narrow and ineffective, and he is right about the
narrowness: a list only finds companies someone already thought of, and
the companies worth finding early are the ones nobody has listed yet.

## Decision

The list grows on its own. Nightly, before the boards are polled, six
remote job feeds and the month's Hacker News "Who is hiring" thread are
read. A posting that hits the intersection terms and links to a
Greenhouse, Lever, Ashby, Workable, SmartRecruiters or Recruitee board
adds that company to the list as pollable, so its whole board is watched
from then on. A posting with no board is stored as a posting under a
hand-check company. Discovered companies carry no tier, so an unlisted
salary fails them and a listed one competes on merit. Caps bound the
growth per night. Job boards are still never scraped; only documented
feeds and public APIs are read.

## Tradeoff accepted

The list fills with companies Matt never chose, and the poll gets longer.
The gates and the tier rule keep the digest honest; `stale` and a tier
edit are how a discovered company is kept or dropped.
