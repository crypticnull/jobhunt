# ADR-0012: Motion is a token table with a reduced column

Date: 2026-09-05

## Status

Accepted.

## Context

The site is meant to be the proof of interaction and systems design for the
roles the search is reaching, design engineer and product designer at product
companies. The adversarial review of 2026-09-05 found it carried one
hard-coded 120ms transition, no named duration or curve, and a reduced-motion
block that set every animation on the page to 0.01ms with `!important`. That
is motion switched off rather than designed away, and it is the pattern a
design engineer interview asks about.

## Decision

Every movement the site makes is a named custom property on `:root` in
`Layout.astro`, with two columns: the value, and what it becomes under
reduced motion. A colour change and an opacity fade are not movement and keep
their durations. Anything that changes position becomes a cut with the same
end state, and the one autonomous animation, the record dot, becomes a steady
dot beside a label that carries the state. The reduced column applies the
same three-state way as the theme: the system preference unless the visitor
said otherwise, and `data-motion` on the root for a specimen page or a test.
A component only ever writes a token, never a number.

## Consequences

The table is a comment beside the tokens today. The next step is the record,
`data/design/tokens.json`, rendered into this block at build and into a
`/system` page, with a CI guard that fails on any literal in a component. That
is the direction the review set and this is its first commit.
