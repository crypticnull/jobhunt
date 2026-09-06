# ADR-0014: The wireframe is the site, and a mask is what renders where a record is missing

Date: 2026-09-06

## Status

Accepted.

## Context

The layout, the motion and the interactions have to be designed before the
content exists. Six project records are placeholders, no chapter has been
written, and the studies wait on exports, boards and stills that arrive on
their own schedule over months. Designing against that means either designing
against empty pages, which teaches nothing about density or rhythm, or
building a separate wireframe, which is a second copy of the site that starts
drifting the day it is made and has to be deleted by hand later.

The home page already decided, in ADR terms if not in an ADR, that a visitor
never sees placeholder tiles: a grid of boxes saying "hero still pending"
costs more credibility than the work earns. That decision stands and this one
has to live beside it.

## Decision

A mask is what renders where a record is absent. It is `display: none` on the
live site and visible in wire mode, so the public page is unchanged and the
same page in wire mode is the finished shape at true size. Wire mode is a
session key set from `?wire` in the URL, stamped before paint alongside the
theme so nothing flashes, and it is never offered in preferences because it is
a tool for building the site rather than a choice for reading it.

A mask never fakes words. A text slot draws rules at the real line height and
measure, which is what you need to judge density, and names what belongs there
and what has to be produced before it can be filled. Lorem would make the page
look finished, and looking finished is the one thing a wireframe must not do.

`/wire` renders the inventory from the same collections the pages read: every
slot filled or masked, every study's missing chapters, and every interaction
marked built or still open.

## Consequences

There is no wireframe to keep in step, because the wireframe is the site with
one attribute set. Every box disappears on its own the day its record lands,
so the inventory empties itself and nothing has to be deleted at the end. The
cost is a handful of hidden elements in the built HTML wherever content is
missing, which shrinks to nothing as the site fills, and one more rule that
any wire-only element has to name its own display value, because CSS has no
keyword that puts an author's `display` back.

The inventory made one thing visible immediately: two of the four motion
durations in the token record are documented on `/system` with play buttons
and performed nowhere on the site. A design system that documents motion the
product does not have is a brochure. Either the open interactions claim those
durations or they come out of the record.
