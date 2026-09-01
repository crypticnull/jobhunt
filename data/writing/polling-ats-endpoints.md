---
slug: polling-ats-endpoints
title: Polling ATS endpoints instead of scraping job boards
date: "2026-09-01"
summary: The job boards fight bots and forbid scraping, but the systems behind them publish clean JSON for anyone who asks politely, so the search runs on a company list instead of a crawler.
draft: false
linked_pipelines: []
---

Every job search tool I looked at wanted to scrape LinkedIn or Indeed, and every one of them was either broken or about to be. The boards fight bots, their terms forbid it, and the markup changes under you every few weeks. I didn't want a tool I'd be repairing on Sunday mornings for nine months, so I went one layer down.

Almost every company posts jobs through an applicant tracking system, and most of those systems publish a public JSON endpoint per company. Greenhouse has one, Lever has one, Ashby has one, and so do SmartRecruiters, Recruitee and Workable. No key, no login, no scraping, just a URL with the company's slug in it and a structured list of open roles on the other end. The boards are a lossy copy of that data. The endpoints are the source.

That flips what the tool is. It's not a crawler, it's a poller against a list of companies I actually want to work for, and the list is the asset. I already needed one for outreach, so the two efforts share a file. Adding a company means pointing the tool at its careers page. It works out which system is behind it by looking at the URL, or at the board links embedded in the page, and it confirms the guess against the live endpoint before it writes anything.

```
python -m scraper add https://jobs.lever.co/example --category ai-video
python -m scraper check
python -m scraper poll
```

Each system gets a small adapter, one module with two functions, the endpoint for a board and a parser that turns the payload into the same normalized posting every other adapter emits. The parser is where the platforms differ in ways that matter. Lever and Ashby tell you outright whether a role is remote, but Greenhouse makes you read the location text. SmartRecruiters won't give you a description at all without a second call per posting, so that adapter follows each one and caps itself at sixty, and a big board can't turn a nightly poll into hundreds of requests. Pay is the same story, structured on Ashby, sometimes on Lever, almost never on Greenhouse. A cheap regex pulls a range out of the description text when the platform published none, and a posting with no comp gets flagged rather than dropped.

Everything lands in SQLite through one module, and that module is the only thing allowed to write the database. A posting is fingerprinted by the platform's own id when it gives one, otherwise by a hash of the company and the normalized title, so the same role never shows up twice across polls. When a posting stops appearing it's closed, never deleted, and it reopens if it comes back. Status is a log rather than a column, because a long search wants to know when something moved, not just where it stands now.

The part I care about most is that nothing is a gate. The search protocol is a scoring config, weights for remote authenticity, seniority, the terms that signal the intersection I'm hiring into, penalties for agency grind, comp against a band, freshness. Every rule adds a signed number and a reason, and the total lands on the row with the ruleset version, so when I tune the weights I can rescore nine months of history and see what would've changed. A weekly digest sorts the open postings into strong, borderline and comp not posted, and every entry carries the reasons that put it there. Borderline is the lane that matters, because a tool that silently drops the interesting edge cases is worse than no tool. The digest also carries a footer that names any source that errored or returned nothing twice running, so when an endpoint changes shape I find out inside a week. I refresh the recorded fixture from the live payload, and the failing test shows me exactly which field moved.

It runs on a Windows workstation from Task Scheduler, nightly poll, nightly backup off the disk, Sunday digest. The whole thing is standard-library Python with no runtime dependencies, which was a deliberate choice, because every dependency is a thing that rots while you aren't looking, and this has to keep working for months without me touching it. The one honest weak spot is Workable, whose widget API is unofficial and has churned before, so that adapter shipped last and has the fixture refresh procedure pointed at it.

The boards were never the problem I needed to solve. The problem was reading a hundred postings a week to find the three worth an evening, and a poller with a scoring config and a digest that explains itself does that on schedule instead of on willpower.
