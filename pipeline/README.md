# pipeline

Asset intake and data validation for `/data`. Python, standard library only.

Today: `python -m pipeline.validate` checks the JSON records against the
schemas in `data/schema` (a deliberate JSON Schema subset, see the module
docstring), and `tests/` carries the repo guarantees, the privacy split
above all. Milestone 10 adds the filename token parser and the media ingest
probe that writes dimensions and posters into project records.
