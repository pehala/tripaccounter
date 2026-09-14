import { html } from '../h.js';

// Plain Bootstrap button + `.collapse` div, no custom JS state (same idiom as
// SplitEditor.js). `parentId`, if given, makes every section sharing it an
// accordion via `data-bs-parent`. Callers own the id scheme
// (`sec-{ownerId}-{group}` bodies, `sec-accordion-{ownerId}` parent) — safe to
// reuse across pages only because statistics and balances are never mounted at once.
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
