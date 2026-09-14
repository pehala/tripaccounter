import { html } from '../h.js';
import { toggleCollapse, showCollapse } from '../collapse.js';

// Links are plain `<a href="#id">` — the tab is the URL path (Trip.js's `tab`
// prop), not the hash, so native anchor scrolling, copy-link and open-in-tab
// all work for free (`scroll-margin-top` in app.css clears the sticky header).
// Each card's own link also toggles its sub-links via the Collapse API in
// onClick, since `data-bs-toggle` would swallow the anchor's own scroll.
// No Bootstrap `.list-group` here: nested inside a `.list-group-item` its
// border mis-renders past the first collapsed entry.
function NavEntry({ id, label, groups }) {
  const bodyId = `nav-${id}-body`;

  return html`
    <div class="border rounded mb-2">
      <a href="#cur-${id}" class="btn w-100 text-start d-flex align-items-center gap-2 px-3 py-2"
         onClick=${() => toggleCollapse(bodyId)}>
        <span class="badge text-bg-primary">${label}</span>
        <i class="bi bi-chevron-down ms-auto"></i>
      </a>
      <div class="collapse" id=${bodyId}>
        <div class="d-flex flex-column border-top py-1">
          ${groups.map((g) => html`
            <a key=${g.key} href="#sec-${id}-${g.key}" class="btn text-start ps-4 py-1 small"
               onClick=${() => showCollapse(`sec-${id}-${g.key}-body`)}>${g.title}</a>
          `)}
        </div>
      </div>
    </div>
  `;
}

// `entries: {id, label, groups: [{key, title}]}[]`. Order (e.g. Total first)
// and content are entirely the caller's responsibility.
export function SideNav({ entries, ariaLabel }) {
  return html`
    <nav class="side-nav" aria-label=${ariaLabel}>
      ${entries.map((entry) => html`<${NavEntry} key=${entry.id} id=${entry.id} label=${entry.label} groups=${entry.groups} />`)}
    </nav>
  `;
}

// Phone-width companion: currency-only pills, no sub-links — each currency's
// sections are close together once you land there, so a second-level jump
// isn't worth the width it would cost on a narrow screen.
export function MobilePillNav({ entries }) {
  return html`
    <div class="d-md-none sticky-top side-nav-mobile mb-2 bg-body-tertiary py-1">
      <div class="nav nav-pills flex-row flex-nowrap overflow-x-auto gap-1">
        ${entries.map((entry) => html`
          <a key=${entry.id} href="#cur-${entry.id}" class="nav-link text-nowrap border-0 bg-transparent">
            <span class="badge text-bg-primary">${entry.label}</span>
          </a>
        `)}
      </div>
    </div>
  `;
}
