// Site-wide copy and links, read from data/identity.json so the site, the
// letters and the resume cannot disagree about the name or the sentence. The
// hero sentence is the positioning thesis: it says what he is, and the motion
// work is the proof underneath it. Edit the record, not this file.
import identity from "../../data/identity.json";

export const site = {
  name: identity.name,
  hero: identity.hero,
  sub: identity.sub,
  github: identity.github,
  // Rendered only when non-empty.
  email: identity.email,
  location: identity.location,
};
