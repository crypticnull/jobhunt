# 0007: Video self-hosted on R2

Date: 2026-09-01
Status: accepted

## Context

Roughly ten portfolio videos need high visual quality, total poster
control, zero layout shift and no third-party branding. Managed players
add JS weight and cost; free embeds add branding and tracking.

## Decision

Hand-tuned progressive MP4s, plus an HLS ladder for longer pieces, on
Cloudflare R2 behind the site's domain, native video elements with local
posters and CSS aspect-ratio. The content model stays host-agnostic;
Bunny Stream, about $1 a month as of September 2026, is the fallback.

## Tradeoff accepted

Encoding is manual and the encode script becomes repo content, which is
the point. No analytics on plays.
