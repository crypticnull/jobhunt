# data

The shared spine. Every package reads through the schemas in `data/schema`,
and every store has exactly one writer. This table is the architecture
diagram.

| Store | Schema | Writer | Readers |
| --- | --- | --- | --- |
| `data/companies.json` | `company.schema.json` | the nightly discovery step, and anyone through `scraper add` or `import`; the nightly task pushes it | scraper, letters |
| `data/local/companies.notes.json` | (sidecar, keyed by slug) | Matt | merged into the list on load |
| `data/companies.example.json` | `company.schema.json` | Matt | tests, the demo |
| `data/projects/<slug>/index.md` + `assets/` | `project.schema.json` | Matt, helped by `pipeline ingest` (milestone 10) | site, letters |
| `data/pipelines/<slug>/index.md` + `assets/` | `pipeline.schema.json` | Matt | site, letters |
| `data/proof/<id>.md` | `proof.schema.json` | Matt | letters, site |
| `data/scoring.json` | `scoring.schema.json` | Matt, twin of `docs/search-protocol.md` | scraper, letters (the proof lead) |
| `data/local/scoring.local.json` | `scoring.schema.json` | Matt | scraper (the comp floor and bands, merged over the public file) |
| `data/voice/rules.json` | (milestone 5) | Matt | voicelint |
| `data/design/tokens.json` | `tokens.schema.json` | Matt | `tools/tokens.mjs` renders it to `site/src/styles/tokens.css`, committed, and `tools/check_tokens.mjs` fails CI when that file is stale or a text pair falls under 4.5 to 1 |
| `data/local/postings.db` | `db/schema.sql` | `scraper/store.py` only | digest, letters read-only |
| `data/digests/` | | `scraper/digest.py`, pushed by the Sunday task | Matt, and Claude from chat |
| `data/last-run.json` | | `scraper/poll`, pushed nightly | the digest, and Claude, to see a job that stopped |
| `data/local/letters/` | | letters (milestone 7) | Matt |

Two rules hold it together. No package imports another; they meet only
here. And `data/local/` is the private half of the search: contacts and notes
on companies, postings.db, letters, and the brief's figures. It
never touches git. The company list and the digests are public (ADR-0010). Create it locally; the ignore rule and the pre-commit
guard keep it out.

## Validation

`make validate` checks the JSON records against their schemas with
`pipeline/validate.py`. The markdown records are validated by the site
build through zod mirrors of the same schemas, and `tools/check_drift.mjs`
fails CI if a mirror and its schema disagree. `db/schema.sql` is a readable
dump of the database; the migrations in `scraper/migrations` are the truth,
and a test keeps the dump equal to them.
