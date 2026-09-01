# 0005: Site framework, Astro 7

Date: 2026-09-01
Status: accepted

## Context

The site needs a typed content model over markdown records, responsive
images without layout shift, and static output. The honest alternative
was plain HTML with a small build script and total control.

## Decision

Astro 7, static output, pinned at the current major, lockfile committed,
no experimental flags, majors ignored until after the search. The only
npm tree in the repo lives in /site.

## Tradeoff accepted

One framework dependency and its churn risk, accepted because content
collections and image handling buy back evenings that go to applications.
