# 0002: The privacy split

Date: 2026-09-01
Status: accepted

## Context

The repo is public and its intended readers include hiring managers at
target companies. The search itself, salary, targets, contacts, letters,
postings, is confidential, and git history is forever.

## Decision

data/local/ is gitignored and holds the private half: the brief's figures,
the real company list, postings.db, digests, letters, contacts. Public
files reference it, never quote it. A pre-commit guard refuses .db files
and data/local paths, and a test asserts the ignore rule. The brief was
sanitized and main's history rewritten on 2026-09-01 to remove figures
that had been committed.

## Tradeoff accepted

GitHub may serve the pre-rewrite commits by SHA until support purges them,
and redacted example files must stand in for real data in tests and demos.
