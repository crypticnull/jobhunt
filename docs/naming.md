# Asset naming

Every file dropped for the site is named so the file alone says what it is,
which project it belongs to, and where it goes in the record. `pipeline
ingest` refuses anything that does not parse and prints the corrected form.

```
{project}_{year}_{deliverable}_{stage}_v{NN}.{ext}

quest_2025_logo-loop_final_v03.mp4
quest_2025_key-art_hero_v01.png
quest_2025_key-art_still_v02.jpg
nitro-create_2026_logo-loop_storyboard_v01.jpg
summit_2025_opener_styleframe_v04.png
bill-of-rights_2024_video_final_v01.mov
game_2026_title-screen_breakdown_v01.png
```

| Token | Rule |
| --- | --- |
| project | the franchise or project slug, lowercase, hyphens inside: `quest`, `nitro-create`, `bill-of-rights`, `game` |
| year | four digits; `{project}-{year}` is the record slug, so `quest_2025_…` lands in `data/projects/quest-2025/` |
| deliverable | what the file is a piece of: `logo-loop`, `key-art`, `opener`, `animation-package` |
| stage | one of the table below |
| vNN | two or three digits, `v01` upward; the highest version of a deliverable and stage wins |
| ext | `mp4`, `mov`, `webm` for finals; `jpg`, `png`, `webp`, `svg` for everything else |

| Stage | Media | Where it goes |
| --- | --- | --- |
| final | video | probed for width, height and duration into `video`, a poster frame extracted; the file itself never enters the repo |
| hero | image | `assets/hero.{ext}` and the `hero` field, required on every record |
| poster | image | `assets/poster.{ext}` and `video.poster`, overriding the extracted frame |
| still | image | `assets/{deliverable}_still_vNN.{ext}` and an entry in `stills` |
| storyboard, styleframe, wip, breakdown | image | `assets/…` and an entry in `process` with that kind |

Underscores separate tokens and hyphens live inside them, so a deliverable
can be two words and the parser never guesses. Alt text and captions are
kept across re-runs when the source path is unchanged; everything else in
`hero`, `video`, `stills` and `process` is regenerated from the assets on
disk, which is why those fields are never edited by hand. The rest of the
record, title, summary, tools, is yours and passes through untouched.
