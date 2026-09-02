// The masthead and the colophon print the commit the page was built from, so
// what you are looking at can always be traced to a tree. CI passes the sha in;
// a local build reads git; neither is available in a tarball, so it degrades to
// a hyphen rather than throwing or printing something untrue.
import { execFileSync } from "node:child_process";

function fromGit() {
  try {
    return execFileSync("git", ["rev-parse", "--short=7", "HEAD"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

const sha =
  process.env.CF_PAGES_COMMIT_SHA?.slice(0, 7) || process.env.GITHUB_SHA?.slice(0, 7) || fromGit() || null;

export const build = {
  sha,
  // Printed rather than the sha alone, because "built 2026-09-02" is the part a
  // person reads and the sha is the part they click.
  date: new Date().toISOString().slice(0, 10),
  href: sha ? `https://github.com/crypticnull/jobhunt/commit/${sha}` : null,
};
