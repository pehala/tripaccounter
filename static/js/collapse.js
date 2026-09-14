// Tiny wrappers around Bootstrap's Collapse API. Used where a click also needs
// to open/toggle a section that isn't the click's own native `data-bs-toggle`
// target — e.g. a sidebar link whose `href` must still scroll natively, which
// `data-bs-toggle="collapse"` on an <a> would otherwise prevent.
export function toggleCollapse(id) {
  const el = document.getElementById(id);
  if (el && window.bootstrap) window.bootstrap.Collapse.getOrCreateInstance(el, { toggle: false }).toggle();
}

export function showCollapse(id) {
  const el = document.getElementById(id);
  if (el && window.bootstrap) window.bootstrap.Collapse.getOrCreateInstance(el, { toggle: false }).show();
}
