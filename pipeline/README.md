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
| `encode.py` | a final to a web ladder under `data/local/encodes`, the R2 URLs into the record, the wrangler upload commands |
| `validate.py` | JSON records against `data/schema`, `make validate` in CI |

## Video

```
python -m pipeline.encode encode drop/quest_2025_logo-loop_final_v03.mp4 --slug quest-2025
python -m pipeline.encode upload quest-2025 --bucket portfolio-media --run
python -m pipeline.encode publish quest-2025 --base-url https://media.<domain>
```

Hand-tuned x264 at 1080 and 720 plus an HLS rendition, written under
`data/local/encodes` so nothing heavy enters the repo (ADR-0007). publish
sets `provider: r2` and the URLs on the record and leaves what ingest
probed alone. The site's player is host-agnostic, so moving hosts is a
different base URL and a re-upload.

## Validation

`python -m pipeline.validate` checks the JSON records against the schemas
in `data/schema` (a deliberate JSON Schema subset, see the module
docstring). The markdown records are validated by the site build through
zod mirrors of the same schemas, so `make site` after an ingest is the
check that the record still builds.

## Publishing a ComfyUI graph

A workflow saved from the ComfyUI canvas carries the node positions, which is
what makes the structure drawable rather than merely listable. It also carries
`widgets_values`, which is every text box in the graph: prompts, model
filenames, LoRA names, seeds and the absolute paths on the machine it ran on.
Nothing raw goes in the repository.

```
python -m pipeline.graph sanitize raw-export.json data/pipelines/<slug>/graph.json
python -m pipeline.graph stats data/pipelines/<slug>/graph.json
python -m pipeline.graph svg data/pipelines/<slug>/graph.json site/public/graphs/<slug>.svg
```

`sanitize` rebuilds the export from an allowlist rather than deleting known-bad
keys, so a field a future ComfyUI version invents is dropped by default instead
of published by oversight. It prints the group titles it carried through, since
those are typed by hand and are the one string worth reading before publishing,
and it names any Note nodes it kept as empty boxes.

`svg` writes a standalone drawing with its own light and dark styles, meant to
be referenced from an `img`, which cannot inherit the page's tokens. Both
commands refuse a file that still carries values, and
`pipeline/tests/test_graph.py` re-checks every graph JSON committed under
`data/` on every test run, so a raw export dropped in later fails in CI rather
than on a stranger's screen.

Save from ComfyUI in the **UI format**, not the API format. The API format has
no node positions, so the graph can be counted but not drawn.
