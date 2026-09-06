# Product motion, the vocabulary

A crash course written against this repo rather than in general. Everything
below already exists here in some form. The point is to give it names, so the
next decision is argued rather than felt, and so the reasoning survives being
written down.

## 1. What the controllers are

`/wire/motion` is a **motion lab**, sometimes a parameter workbench. Its
ancestor is the type specimen: a sheet that shows one typeface at every size
and weight so a decision gets made by looking rather than by describing. The
motion version adds live parameters, because a duration cannot be judged from
a number and a curve cannot be judged from four decimals.

Large design systems have these internally. Material, Carbon, Lightning and
Polaris all shipped motion specs, and the teams behind them all built private
tools to tune them. Almost nobody publishes one. A public lab where a stranger
can drag a slider and feel the difference is rare enough to be a portfolio
piece in itself, not just the tool that made the site.

The value is not that it produces better numbers. It is that it makes taste
**reproducible**. A decision made in the lab comes with the alternatives it
beat, which is the difference between a preference and an argument.

## 2. Three tiers, and where this repo sits

The standard token architecture, in the W3C Design Tokens vocabulary, has
three layers.

| Tier | Name | Example |
| --- | --- | --- |
| 1 | primitive, or global | `grey-400`, `300ms` |
| 2 | semantic, or alias | `--ink`, `--enter-overlay` |
| 3 | component | `--card-hover-bg` |

Tier 1 says what a value **is**. Tier 2 says what it is **for**. The whole
benefit of a token system lives in tier 2, because that is the layer where one
edit changes every place a meaning appears, and where a component never has to
know a number.

The colour record here is already tier 2 and reads unusually well:

```
paper   page ground
ink     text, the H1, rules on plates
muted   secondary text, captions, nav at rest
rule    1px hairlines only, never text
marker  the one accent: frame numbers, hover, focus, the record dot
```

Not one of those names is a colour. They come out of print, and they describe
a job. `marker` can go from orange to green and every use stays correct.

The motion record is not tier 2. It is tier 1 wearing tier 2's clothes:

```
t-quick   120ms
t-fade    380ms
t-slide   230ms
t-blink   500ms
```

`fade`, `slide` and `blink` are mechanisms, not jobs. Which is fine until one
mechanism has to serve two jobs with opposite needs.

## 3. The fade, which is the whole lesson

`--t-fade` currently drives at least four movements:

| Movement | Distance | What it is |
| --- | --- | --- |
| hero rise on first paint | 8px | gates reading |
| still growing to full size | several hundred px | the drama moment |
| slip tint under a hovered word | none, opacity only | a response to the pointer |
| plate crossfade | none, opacity only | a state change |

One number cannot be right for all four, so tuning it for any one of them
breaks the others silently. That is a **token collision**, and the cure is
never a compromise value. It is a split by role.

A proposal, keeping every value that got dialled in and changing only the
names and the wiring:

```
--respond        120ms   hover tint, focus, press, the slip fringe
--enter-page     200ms   the hero rise, because it stands between a
                         reader and the sentence
--enter-overlay  480ms   the still growing from its tile, the one place
                         the page is allowed to perform
--move-mark      230ms   the chapter rail
--pulse          500ms   the record dot
```

The slow fade and the quick entrance stop being in conflict, because they were
never the same decision.

## 4. Duration is a function of distance

The most useful law in the field, and the reason the argument happened.

Perceived speed is distance over time. A fixed duration therefore reads as
sluggish on a short move and rushed on a long one. Material calls the fix
dynamic duration. In practice:

- Under about 100px: 100 to 150ms
- Across a card or a row: 200 to 300ms
- Across most of the viewport: 300 to 500ms
- Full screen, or a shared element flying across the page: 400 to 600ms

380ms over 8 pixels is slow. 380ms over 600 pixels is brisk. Both statements
are about the same number and neither is about taste.

## 5. Two classes of motion, and where taste actually lives

This is the real answer to whether there is room for drama.

**Responsive motion** answers an input. Hover, press, focus, toggle, a field
accepting a keystroke. The user is waiting for it, so the budget is roughly
100 to 200ms. Under about 100ms it reads as instant. Past about 200ms it reads
as lag, and past 300ms people start clicking again because they think it
missed. There is genuinely no room for flair here, and that is not a matter of
fashion. It is a matter of the movement being in the way.

**Expressive motion** is the system narrating. A page arriving, an overlay
opening, an empty state, a success, a transition that explains where a thing
went. Nobody is blocked, so the budget is 300 to 600ms and can run longer when
the movement carries meaning. This is where taste, drama and signature live,
and a system with none of it feels like a spreadsheet.

So the rule is not fast good, slow bad. It is: **know which class a movement is
in, and spend the budget for that class.** A designer with a recognisable hand
is one who found the expressive moments and made them count while keeping the
responsive ones out of the way. The misregistration idea is a good instinct
badly placed if it runs at overlay speed, and it is a signature at 120ms.

One caveat that cuts across both. An entrance that gates content is charged
against the reader's time even though nothing is blocked. That is why the hero
gets the tightest expressive budget on the site.

## 6. Easing carries meaning

- **ease-out** for anything arriving. Fast at the start, settling at the end.
  Attention lands on the arrival, and the object feels like it had momentum
  and stopped.
- **ease-in** for anything leaving. Slow, then gone. The exit is not worth
  watching.
- **ease-in-out** for anything moving from one place to another while staying
  on screen.
- **linear** only for continuous or looping motion. Spinners, progress, a
  blinking dot. Anything with a beginning and an end reads as mechanical under
  linear.

`ease-out` for entering and `ease-in` for leaving is already what this record
says, which is the correct pairing and one that plenty of shipped systems get
backwards.

## 7. Five properties, and the one this repo does that most do not

Every motion decision is five values.

1. **Duration**
2. **Easing**
3. **Delay**, including stagger across a group
4. **Distance**
5. **Trigger**, what causes it

Most design systems tokenise the first two and leave the rest to whoever
writes the component. This one tokenises distance as well:

```
slip-x    0.34em   how far a misregistered word slips
rise-y    0.5rem   how far the hero rises on first paint
press     0.985    how far a pressed thing gives
slip-band 13rem    how wide the pointer's influence reaches
```

That is unusual and it is the right instinct. Distance is half of perceived
speed, so a system that tokenises duration and not distance has only tokenised
half of each decision. Worth saying out loud in the writing section, because
it is the sort of detail that reads as a person who has actually run a system
rather than read about one.

`slip-band` goes further and tokenises the **field** of an interaction, which
is closer to a game or a shader than to a web component.

## 8. Choreography, which is the part not built yet

Single movements are the easy half. The vocabulary for the rest:

- **Stagger**, or cascade. A group entering with a fixed offset between
  members, so the eye reads an order instead of a wall. 30 to 60ms per item,
  and it needs a cap, because twelve items at 50ms is a slideshow.
- **Follow-through**. A secondary element arriving a beat after the primary.
  Already in the hero, described as "the sub a beat behind".
- **Shared element transition**. One object persisting across a navigation
  while everything else changes. This is exactly what B2, the still that
  holds, is. It has a name, it is the strongest craft signal in the whole
  decision set, and it now has a native browser API in View Transitions, so
  it costs far less to build than it did two years ago.
- **Orchestration**. The rule for what happens when two animations want the
  same element. Almost every system discovers it needs one only after a bug.

## 9. Reduced motion is a decision per movement

The two column motion record here, one value and one for reduced, is ahead of
most published systems, so it is worth knowing why it is right.

`prefers-reduced-motion` is usually implemented as a kill switch that zeroes
every duration. That overshoots. The vestibular response the setting exists to
protect against is triggered by large area movement, parallax, spin and zoom.
Opacity and colour do not trigger it. WCAG 2.3.3 asks for motion that is not
essential to be removable, not for all change to be removed, and a hard cut
between two stills is worse for a reader with a vestibular disorder than a
short crossfade.

So the correct shape is a decision per movement, which is what this record
already holds:

```
t-quick   120ms -> 120ms   a colour change is not movement
t-fade    380ms -> 380ms   opacity is not movement
t-slide   230ms -> 0ms     position change becomes a cut, same end state
t-blink   500ms -> 0ms     becomes a steady dot, and a label sits beside it
```

The last one carries a second principle worth naming: **motion is never the
only signal**. A blink that stops still leaves a dot and a word.

## 10. Where to read further

- Material Design 3, the motion section, for dynamic duration and for
  easing tokens named by role
- IBM Carbon motion, the clearest published writing on productive against
  expressive motion, which is the same split as section 5
- Val Head, *Designing Interface Animation*, the standard text, and the
  source for most of the timing bands above
- Rachel Nabors on accessible motion, for why the kill switch is wrong
- The W3C Design Tokens Community Group format spec, for the tier vocabulary
- Apple Human Interface Guidelines, motion, for the shared element case

## 11. Why this is worth saying out loud on the site

The market has plenty of people who can feel a forty millisecond difference
and cannot say why, and plenty who can name every tier of a token architecture
and cannot tell when a curve is wrong. The lab is proof of both at once, in a
form a stranger can operate in ten seconds without reading anything.

That is worth a build entry and a writing post, not just a tool that made the
site.
