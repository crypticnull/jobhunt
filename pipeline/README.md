# pipeline

Asset intake and data validation for `/data`. Python, standard library
only (ADR-0004), with ffprobe and ffmpeg called as external binaries for
video, since they are on the workstation already.

## Intake

```
python -m pipeline.ingest path/to/drop [--slug quest-2025] [--dry-run]
```

Files are named per `docs/naming.md`, `{project}_{year}_{deliverable}_{stage}_vNN.{ext}`,
and one bad name refuses the whole drop with the corrected form printed.
Images are copied into `data/projects/<slug>/assets/` under canonical names
and sized from their headers. A final video is probed for size and duration
and a poster frame is pulled from it; the video itself never enters the
repo. Then the record's `hero`, `video`, `stills` and `process` fields are
rewritten from what is on disk, alt text and captions carried over where
the source path is unchanged, and every other line of the record passes
through untouched. A drop for a project with no record scaffolds one with
TODO markers, provided it carries a hero still.

| File | Job |
| --- | --- |
| `naming.py` | the token spec as a parser; a refusal carries the suggested name |
| `media.py` | png, jpeg, gif, webp and svg sizes from headers; ffprobe and ffmpeg for video |
| `frontmatter.py` | read and rewrite the records' flow-style frontmatter without a YAML library |
| `ingest.py` | the drop to record fields |
| `validate.py` | JSON records against `data/schema`, `make validate` in CI |

## Validation

`python -m pipeline.validate` checks the JSON records against the schemas
in `data/schema` (a deliberate JSON Schema subset, see the module
docstring). The markdown records are validated by the site build through
zod mirrors of the same schemas, so `make site` after an ingest is the
check that the record still builds.
