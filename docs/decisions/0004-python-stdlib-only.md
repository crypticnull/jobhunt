# 0004: Python, stdlib only

Date: 2026-09-01
Status: accepted

## Context

The scraper, letters and pipeline packages run unattended for months on
one Windows workstation. Every dependency is a thing that can rot, break
on update, or need an environment story.

## Decision

Python 3.12, standard library only: urllib, sqlite3, json, argparse,
unittest. No runtime dependencies, no test framework beyond unittest.
ffmpeg is invoked as an external binary where media probing needs it.

## Tradeoff accepted

Some code is longer than a library would make it. That is fine; the
restraint is legible and nothing rots.
