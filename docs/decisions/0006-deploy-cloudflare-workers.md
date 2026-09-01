# 0006: Deploy on Cloudflare Workers static assets

Date: 2026-09-01
Status: accepted

## Context

As of September 2026, Cloudflare Pages is in maintenance mode, and
Netlify's credit system can pause a free site mid-search. A portfolio
that goes dark during a job search is the worst possible failure.

## Decision

Cloudflare Workers static assets on the free tier, behind a purchased
domain from the first deploy, about $12 a year.

## Tradeoff accepted

Ties deploy and video hosting to one vendor. Acceptable because
everything is static files that can move anywhere in an afternoon.
