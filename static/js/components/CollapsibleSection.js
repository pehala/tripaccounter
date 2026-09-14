import { html } from '../h.js';

// Same collapse idiom as SplitEditor.js: a plain Bootstrap button + `.collapse`
// div, no custom JS state. Collapsed by default (`defaultOpen` opts a
// particular section in, e.g. balances' settle-up — the one figure worth
// seeing without a click) so a currency with several sections stays
// scannable; `summary` (if given) stays visible even while collapsed.
// `parentId`, if given, makes every section sharing it an accordion —
// opening one closes the others under the same parent — without adopting
// Bootstrap's `.accordion` visual classes; worth it for statistics' four
// sections, not for balances' two short ones, so it's optional. Callers own
// the id scheme (`sec-{ownerId}-{group}` bodies, `sec-accordion-{ownerId}`
// parent when used — statistics and balances are never mounted at once, so
// the two pages never collide even reusing the same scheme).
export function CollapsibleSection({ id, parentId, icon, title, summary, children, defaultOpen = false }) {
  const bodyId = `${id}-body`;

  return html`
    <div id=${id} class="border rounded mb-2">
      <button class="btn btn-sm w-100 text-start d-flex align-items-center gap-2 py-2" type="button"
              data-bs-toggle="collapse" data-bs-target="#${bodyId}">
        <i class="bi ${icon}"></i>
        <span class="fw-semibold">${title}</span>
        ${summary && html`<span class="text-body-secondary ms-auto small">${summary}</span>`}
        <i class="bi bi-chevron-down"></i>
      </button>
      <div class="collapse ${defaultOpen ? 'show' : ''}" id=${bodyId} data-bs-parent=${parentId ? `#${parentId}` : undefined}>
        <div class="px-3 pb-3 border-top pt-2">${children}</div>
      </div>
    </div>
  `;
}
