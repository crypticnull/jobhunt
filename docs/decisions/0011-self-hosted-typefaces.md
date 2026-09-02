# ADR-0011: Typefaces are vendored, not fetched

Date: 2026-09-02

## Status

Accepted.

## Context

The site design plan sets the pages in three families: Archivo for display,
Source Serif 4 for reading, IBM Plex Mono for anything that is a number, a
path, a label or a caption. The obvious way to get them is a stylesheet from a
font host, and it is the wrong way here for three reasons.

A portfolio whose argument is "I build the pipeline and I care where the assets
live" cannot make a third-party request for its own typography on every visit.
It is a small hypocrisy but it is the kind a technical reader notices.

A hosted stylesheet is render-blocking and adds a DNS lookup, a TLS handshake
and a round trip before any text can paint. The performance budget in
`site/lighthouserc.json` is 90, and the layout-shift budget is zero.

`font-display: swap`, which every font host defaults to, is a layout shift by
design: text paints in the fallback, then reflows when the real face lands.
Zero CLS and swap are not compatible.

## Decision

The five woff2 files live in `site/src/fonts` and are served from this origin.
`astro.config.mjs` declares them through `fontProviders.local()`, so a build
makes no network request and is reproducible from the tree alone.

Every family is `display: optional`. A face that has not arrived in time is
skipped for that page load rather than swapped in late. Astro also emits a
metric-matched local fallback for each family, with `size-adjust` and
`ascent-override` computed against Arial, Times New Roman and Courier New, so
the fallback occupies close to the same space as the real face and the skipped
case does not look broken.

Only the display face and the roman of the reading face are preloaded. The
italic and both mono weights load on demand, because neither is in the first
paint of any page.

The three fontsource packages are deliberately **not** dependencies. They were
installed once in a scratch directory, the latin subsets were copied out, and
the packages were discarded. `site/src/fonts/NOTICE.md` records the exact
package versions and the copy procedure, so refreshing a file is a two-minute
job and nothing has to resolve at install time for the site to build.

All three families are licensed under the SIL Open Font License 1.1, which
permits embedding and redistribution. The copyright holders are recorded in
`NOTICE.md`.

## Consequences

Roughly 368 KB of woff2 is committed to the repository. That is a real cost and
it is paid once; the files are immutable and content-hashed at build, so they
cache forever and never re-download.

Adding a weight or a script means copying another file in and adding a variant,
not changing a URL. That is more friction than a hosted stylesheet, and it is
the right amount of friction for a decision that affects every page.

If the latin subset ever stops being enough, the same provider takes additional
files with `unicodeRange` set per variant.
