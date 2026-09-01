# data

The shared spine. The target company list, project records, proof stories,
pipeline records and scoring config live here, and every package reads
through the schemas in `data/schema`. The full contract table, every store,
its schema, its one writer, its readers, lands with milestone 2.

`data/local/` is the private half of the search and never touches git: the
real company list, postings.db, digests, letters, contacts, and the brief's
figures. Create it locally; the ignore rule and the pre-commit guard keep
it out.
