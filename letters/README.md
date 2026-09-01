# letters

Cover letter blocks, assembly and the voice lint. Python, standard library
only (ADR-0004). The generator arrives in milestone 7; the lint is here
now because nothing in his voice ships without passing it.

## The voice lint

```
python -m letters.voicelint --profile letter [paths]   # letters, proof stories
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
