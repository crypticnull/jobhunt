# ADR-0013: One inline script runs before paint, for the visitor's own preferences

Date: 2026-09-05

## Status

Accepted.

## Context

The site plan promised chrome with no JavaScript, and the pages kept that
promise: zero script tags in the built HTML. The theme tokens honoured a
`data-theme` attribute that nothing ever set, so the third state, an explicit
choice that beats the system setting, was unreachable, and a theme control is
the most recognisable small interaction a product design team ships. A control
that applies after first paint flashes the wrong theme on every visit.

## Decision

A twelve-line inline script in the head reads a stored theme or motion choice
and stamps it on the root before the stylesheet applies, wrapped in try/catch
so a blocked storage API leaves the system setting. The control itself is a
footer component built on native radios, shipped disabled and enabled by its
own script, so without JavaScript it reads as a label. Theme has three states,
system, light and dark. Motion has two, system and reduce, because a person who
asked their system for less motion is not offered a button that argues with
them.

## Consequences

The promise changes from no script to no script that the page needs: every
page is complete without it, and the inline script changes colours and
durations only, so layout shift stays at zero. Any further script on the site
is held to the same rule and named in an ADR.
