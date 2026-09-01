// @ts-check
import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  // The real domain arrives with the first deploy (ADR-0006); CI passes it in.
  site: process.env.SITE_URL || "https://example.com",
  trailingSlash: "never",
  build: {
    format: "file",
  },
});
