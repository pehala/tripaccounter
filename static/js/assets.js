// URL of a file in the static root, e.g. `asset('favicon.svg')`.
// Resolved against this module, so it carries the versioned mount the server serves
// assets under (`/s/<build_id>/`) and falls back to `/` in dev. JS the server never
// rewrites must not hardcode an absolute `/…` path; go through here instead.
const ROOT = new URL('../', import.meta.url);

export const asset = (path) => new URL(path, ROOT).href;
