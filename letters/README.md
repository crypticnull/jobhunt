# letters

Cover letter blocks, assembly and the voice lint. Python, standard library
only (ADR-0004). Nothing here sends anything. The generator drafts, Matt
decides.

## The loop

```
python -m scraper digest --stdout            # pick a posting id from the digest
python -m letters brief 12 [--lead ae-llama] # data/local/letters/briefs/<company>-12.md
                                              # draft the letter from the brief, in a Claude Code session or by hand
python -m letters save 12 draft.md           # lint, then file as data/local/letters/<company>-12-<date>.md
python -m scraper mark 12 applied --letter data/local/letters/<company>-12-<date>.md
```

For a referral or a company without a feed, `python -m scraper add-posting
URL-or-file --company slug --title "..."` makes a normal scored row first.

The brief joins the posting and why it scored, the company record, the
selected blocks with placeholders filled, the lead proof story, and the
voice rules. The save runs the letter profile of the lint and refuses any
draft that does not pass clean, warnings included.

## Blocks

Modular blocks assembled per role, never one template with holes.

| Block | Files | Selection |
| --- | --- | --- |
| opening | `blocks/openings/` | all three offered, pick one and make it name the specific thing |
| claim | `blocks/claims/<category>.md` | by the company's category: ai-video leads with the local pipeline, studio-ai with tooling, product-inhouse with craft plus tooling, brand-inhouse with the event brand systems |
| proof | `data/proof/<id>.md` | `--lead`, else the company's `lead_proof`, else the first story whose `leads_for` includes the category |
| remote | `blocks/remote.md` | only when the posting is hybrid, unclear, or scored as remote-hedged |
| close | `blocks/closes/` | both offered, pick one |

Blocks are markdown with a short frontmatter (`id`, `kind`, `for`, `note`)
and `{company}`, `{role}`, `{specific}`, `{site}` placeholders. Every block
passes the letter profile in CI; the first drafts here are scaffolding for
Matt to rewrite in his own words.

## The voice lint

```
python -m letters.voicelint --profile letter [paths]   # letters, proof stories, blocks
python -m letters.voicelint --profile repo   [paths]   # docs and site source
make lint                                              # both, as CI runs them
```

Output is `path:line:col rule-id message`. Exit 0 clean, 1 on any error, 2
when only warnings fired. Under the letter profile any nonzero exit blocks
a save; the repo profile has no warnings, only the two strongest signals.

| Rule | Letter | Repo |
| --- | --- | --- |
| em-dash | error | error |
| corporate-vocab | error | error |
| semicolon, parentheses, ellipsis, bullet-list | error | off |
| not-x-but-y, formal-signoff, apply-opener | error | off |
| contractions, sentence-length, connector | warning | off |

The lexicon, the contraction table and the profiles live in
`data/voice/rules.json`. A rare false positive is waived inline with
`<!-- voicelint: allow rule-id -->` on the line before, or at the end of
the line. Every rule has a passing and a failing sample in
`tests/samples/`, and the test suite asserts each failing sample trips
exactly its own rule.
