# data

The shared spine. Every package reads through the schemas in `data/schema`,
and every store has exactly one writer. This table is the architecture
diagram.

| Store | Schema | Writer | Readers |
| --- | --- | --- | --- |
| `data/local/companies.json` | `company.schema.json` | Matt, helped by `python -m scraper add` | scraper, letters |
| `data/companies.example.json` | `company.schema.json` | Matt | tests, the demo |
| `data/projects/<slug>/index.md` + `assets/` | `project.schema.json` | Matt, helped by `pipeline ingest` (milestone 10) | site, letters |
| `data/pipelines/<slug>/index.md` + `assets/` | `pipeline.schema.json` | Matt | site, letters |
| `data/proof/<id>.md` | `proof.schema.json` | Matt | letters, site |
| `data/scoring.json` | `scoring.schema.json` (milestone 4) | Matt | scraper |
| `data/voice/rules.json` | (milestone 5) | Matt | voicelint |
| `data/local/postings.db` | `db/schema.sql` | `scraper/store.py` only | digest, letters read-only |
| `data/local/digests/` | | `scraper/digest.py` (milestone 4) | Matt |
| `data/local/letters/` | | letters (milestone 7) | Matt |

Two rules hold it together. No package imports another; they meet only
here. And `data/local/` is the private half of the search: the real company
list, postings.db, digests, letters, contacts, and the brief's figures. It
never touches git. Create it locally; the ignore rule and the pre-commit
guard keep it out.

## Validation

`make validate` checks the JSON records against their schemas with
`pipeline/validate.py`. The markdown records are validated by the site
build through zod mirrors of the same schemas, and `tools/check_drift.mjs`
fails CI if a mirror and its schema disagree. `db/schema.sql` is a readable
dump of the database; the migrations in `scraper/migrations` are the truth,
and a test keeps the dump equal to them.
