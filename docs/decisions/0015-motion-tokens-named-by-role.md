# ADR-0015: Motion tokens are named for the job, not the mechanism

Date: 2026-09-06

## Status

Accepted. Extends ADR-0012, which stands. The two column record and the
component-never-writes-a-number rule are unchanged.

## Context

ADR-0012 gave every movement a name and a reduced value. The names it chose
were mechanisms: `t-quick`, `t-fade`, `t-slide`, `t-blink`. A mechanism is not
a job, so nothing stopped one token from being attached to several unrelated
movements, and `--t-fade` ended up carrying four of them.

| Movement | Distance | Class |
| --- | --- | --- |
| hero rise on first paint | 8px | expressive, and it gates reading |
| still growing to full size | several hundred px | expressive |
| tint under a hovered word | none, opacity only | responsive |
| plate crossfade | none, opacity only | responsive |

Perceived speed is distance over time, so one number cannot be right for all
four. Tuning it for any one of them broke the others with no error and no
visible failure. That is what happened on 2026-09-06: a value dialled while
watching the misregistration made the hero heavier, and the disagreement about
whether 480ms was slow was really a disagreement about which movement was
being discussed.

The colour tokens never had this problem, because they were named `paper`,
`ink`, `muted`, `rule`, `marker` and `blueprint` from the start. Not one of
them is a colour.

## Decision

The duration tokens are renamed for the job, and split where one name was
serving two jobs.

```
--respond        120ms / 120ms   hover, focus, the press, the intent timer
--beat           120ms / 120ms   the gap between the hero line and its sub
--enter-page     200ms / 200ms   the hero rise on first paint
--enter-overlay  480ms /   0ms   the still growing from its tile
--move-mark      230ms /   0ms   the chapter rail mark
--slip           230ms /   0ms   the misregistration offset and its tint
--pulse          500ms /   0ms   the record dot
```

Two classes decide the budget. **Responsive** motion answers an input while
somebody waits, so it is spent in roughly 100 to 200ms and carries no drama.
**Expressive** motion is the system narrating while nothing is blocked, so it
runs 300 to 600ms and is where a signature is allowed to live. An entrance
that stands between a reader and the text is charged against reading time even
though nothing is blocked, which is why `--enter-page` takes the tightest
expressive budget on the site.

Three values change rather than carry over. The hero drops from 380 to 200ms,
because 380 over eight pixels reads as slow. The overlay rises from 380 to
480ms, because 380 over several hundred pixels reads as rushed, and it is the
one place the page should perform. The fringe tint drops from 380 to 230ms and
joins the offset it rides with, because they are one event.

`--enter-overlay` is also the first duration whose reduced value is a real
decision rather than a carry-over: it becomes 0ms, so the dialog opens at its
final place. `Lightbox.astro` already said in a comment that a visitor asking
for less motion got the same travel at 0ms, which the record did not deliver
while the token was shared with a fade.

The dial panel in `/wire/motion` groups its sliders as responsive and
expressive, so the tool states the distinction it enforces.

## Consequences

A movement is tuned without touching any other movement, which is the whole
point and was not true before. The cost is more tokens, seven durations rather
than four, and a naming discipline that has to hold: a new movement gets a new
name when no existing job fits, and reusing a token because its number happens
to be right is the fault this ADR exists to stop.

`docs/motion-vocabulary.md` carries the reasoning at length, including the
timing bands and the reduced-motion rules the classes come from.
