import { html } from '../h.js';

export function LabelBadge({ name }) {
  return html`<span class="badge rounded-pill bg-body-secondary text-body border me-1">${name}</span>`;
}
