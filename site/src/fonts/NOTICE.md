# Vendored typefaces

Three families ship with the site as woff2 rather than being fetched from a
font host at runtime. ADR-0011 has the reasoning. All three are licensed under
the SIL Open Font License 1.1, which permits embedding and redistribution.

| File | Family | Axes | Source |
| --- | --- | --- | --- |
| `archivo-latin-standard-normal.woff2` | Archivo | `wght` 100–900, `wdth` 62–125% | `@fontsource-variable/archivo` 5.3.0 |
| `source-serif-4-latin-standard-normal.woff2` | Source Serif 4 | `wght` 200–900 | `@fontsource-variable/source-serif-4` 5.3.0 |
| `source-serif-4-latin-standard-italic.woff2` | Source Serif 4 italic | `wght` 200–900 | as above |
| `ibm-plex-mono-latin-400-normal.woff2` | IBM Plex Mono | static 400 | `@fontsource/ibm-plex-mono` 5.3.0 |
| `ibm-plex-mono-latin-500-normal.woff2` | IBM Plex Mono | static 500 | as above |

Copyright: Archivo, the Archivo Project Authors. Source Serif 4, Google Inc.
IBM Plex Mono, IBM Corp. Full licence text at
https://openfontlicense.org/open-font-license-official-text/

These are the latin subsets only. To refresh them, install the package version
above in a scratch directory and copy the matching file out of its `files/`
directory. The packages are deliberately not dependencies of the site, because
nothing at build or run time needs them once the file is here.
