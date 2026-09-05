---
id: jobhunt
title: This repo, and the site it builds
leads_for: [product-inhouse, studio-ai]
linked_projects: []
linked_pipelines: []
repo: https://github.com/crypticnull/jobhunt
summary: A job search toolkit and portfolio built in public, with a token and motion system, accessibility and layout shift budgets enforced in CI, and the history left intact as the case study.
order: 8
---

The search runs on this repo. A poller against public ATS endpoints, a scorer that encodes the search protocol as data, and a letter generator with a voice lint that refuses anything that reads as machine-written. The portfolio site sits beside them, and all of it's standard-library Python and one pinned Astro build. The site is held to a zero layout shift budget and to accessibility and performance scores on every push, three runs and the median. It honours reduced motion and both colour schemes, and every number on it comes from a record at build. The decisions are written down the day they're made, twenty five lines each, and the commit history is left alone, because the way I work is the thing that's being sold.
