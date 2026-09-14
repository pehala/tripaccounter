import { html } from '../h.js';
import { toggleCollapse, showCollapse } from '../collapse.js';

// The sidebar links are plain `<a href="#id">`s — the tab is the URL path
// (Trip.js's `tab` prop), not the hash, so the browser's own anchor scrolling
// just works, `scroll-margin-top` (app.css) keeps it clear of the sticky
// header, and a link can be copied or opened in a new tab like any other.

// One collapsible card per entry (a currency, or Total) in the sidebar: the
// whole row is one link that both scrolls straight to that section (native
// anchor navigation) and toggles its sub-links (the Collapse API, so the
// click still opens/closes even though `href` — not `data-bs-toggle` — is
// what would otherwise make Bootstrap swallow the anchor's own default
// action). Each sub-link opens that exact section before scrolling to it.
// Same bordered-card idiom as CollapsibleSection/SplitEditor — a plain
// `.list-group` nested inside a `.list-group-item` mis-renders its border
// past the first collapsed entry, so this sidebar deliberately does not use
// Bootstrap's list-group at all.
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
