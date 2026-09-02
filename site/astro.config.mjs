// @ts-check
import { defineConfig, fontProviders } from "astro/config";

export default defineConfig({
  output: "static",
  // The real domain arrives with the first deploy (ADR-0006); CI passes it in.
  site: process.env.SITE_URL || "https://example.com",
  trailingSlash: "never",
  build: {
    format: "file",
  },
  // Typefaces are vendored as woff2 under src/fonts and served from this
  // origin, so a build needs no network and a visit makes no third-party
  // request (ADR-0011). display:optional is the whole CLS story: a face that
  // has not arrived in time is skipped for that page load rather than swapped
  // in late, which is what holds the layout-shift budget at zero.
  fonts: [
    {
      provider: fontProviders.local(),
      name: "Archivo",
      cssVariable: "--font-display",
      display: "optional",
      fallbacks: ["Helvetica Neue", "Arial", "sans-serif"],
      options: {
        variants: [
          {
            src: ["./src/fonts/archivo-latin-standard-normal.woff2"],
            weight: "100 900",
            style: "normal",
            // The width axis is why this face is here: one file gives both the
            // condensed headline and the normal-width labels.
            stretch: "62% 125%",
          },
        ],
      },
    },
    {
      provider: fontProviders.local(),
      name: "Source Serif 4",
      cssVariable: "--font-body",
      display: "optional",
      fallbacks: ["Georgia", "Times New Roman", "serif"],
      options: {
        variants: [
          { src: ["./src/fonts/source-serif-4-latin-standard-normal.woff2"], weight: "200 900", style: "normal" },
          { src: ["./src/fonts/source-serif-4-latin-standard-italic.woff2"], weight: "200 900", style: "italic" },
        ],
      },
    },
    {
      provider: fontProviders.local(),
      name: "IBM Plex Mono",
      cssVariable: "--font-mono",
      display: "optional",
      fallbacks: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      options: {
        variants: [
          { src: ["./src/fonts/ibm-plex-mono-latin-400-normal.woff2"], weight: 400, style: "normal" },
          { src: ["./src/fonts/ibm-plex-mono-latin-500-normal.woff2"], weight: 500, style: "normal" },
        ],
      },
    },
  ],
});
