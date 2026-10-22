import { html } from '../h.js';
import { t } from '../i18n/index.js';

export function AddToggle({ open, onOpen, disabled = false }) {
  if (open) return null;
  return html`<button class="btn btn-sm btn-outline-primary" type="button" disabled=${disabled} onClick=${onOpen}>${t('action.add')}</button>`;
}
