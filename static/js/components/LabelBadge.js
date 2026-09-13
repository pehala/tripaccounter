import { html } from '../h.js';

export function LabelBadge({ name }) {
  return html`<span class="badge rounded-pill text-bg-light border">${name}</span>`;
}
