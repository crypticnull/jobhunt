# ADR-0016: The desktop app is the way in

Date: 2026-09-06

## Status

Accepted. Supersedes nothing. The console (`scraper/serve.py`) and the digest
files are unchanged and both still work on their own.

## Context

The search had been living in three places at once. The store and the postings'
own words were on his machine, the code and the weekly markdown were on GitHub,
and whatever he could actually see was in a chat window. Every surface built for
him wrote a file and hoped he would find it, so the answer to "what does this job
actually say" was a command, then a file, then a browser, and the file was stale
by the next poll.

The console fixed the staleness. It did not fix the container. A browser tab is
the wrong home for a thing he works in daily: it gets buried behind other tabs,
opened four times over, and closed by accident, and nothing about it says this is
an application rather than a page he visited once.

He also wants the site sandbox in the same place. Designing the portfolio and
working the search are the same evening's work, and they were two servers, two
commands and two windows.

## Decision

One desktop application, `desktop/`, launched by `app.cmd`. It owns two views,
the search console and the Astro dev server, in one window with one taskbar
icon.

This adds Electron, the first dependency outside the site's own Astro tree, and
the ground rules say to ask before adding one. He asked for it directly.

Specifics that are decisions rather than detail:

- **Single instance.** `requestSingleInstanceLock`, so launching it again
  focuses the window that is open. Ending up with six copies fighting over one
  port was the stated complaint, and this is the whole answer to it.
- **The renderer asks, the main process never announces.** A `send` before the
  window has run its script reaches nobody, and a reload loses one that landed.
  Both failures left the window reading "starting the console" over a console
  that had been serving for a minute. State is fetched with `invoke` on every
  load instead, so a reload rebuilds the window from what is actually running.
- **The console is attached to, not restarted.** If it is already listening he
  started it himself, and starting a second one only loses to EADDRINUSE.
- **The site starts on the first click, not at launch.** It is an npm install
  and a dev server, and most evenings he does not want it.
- **Nothing outlives the window.** Children are killed on quit, because a python
  process left holding the store is only noticed at four in the morning.
- **`contextIsolation` stays on and the preload exposes three verbs.** The views
  render text written by strangers, and a job posting must never be one step
  from the file system.
- **Links open in his browser.** A posting's own link in here would turn the app
  back into the browser he asked to stop using.

## Consequences

`app.cmd` is the way in and everything else in `run.cmd` is maintenance. The
first run installs Electron, a few hundred megabytes, once.

The console and the digest still stand alone. The app is a container for them,
not a rewrite of them, so `run.cmd` on its own and the dated digest files keep
working and neither depends on Node.

Electron is now a thing to keep current. It was pinned at 38.2.2 for about ten
minutes, which `npm audit` answered with twenty one high severity advisories, so
it is pinned at 44.2.0 and the audit is clean. That check belongs in the routine
that already watches the other dependencies.
