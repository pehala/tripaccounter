import { html } from '../h.js';
import { t } from '../i18n/index.js';

// The one Edit button: item rows, transfer rows and stay cards all open their modal with it.
export function EditButton({ onClick }) {
  return html`
    <button type="button" class="btn btn-sm btn-outline-secondary py-0" onClick=${onClick}>
      <i class="bi bi-pencil"></i> ${t('action.edit')}
    </button>
  `;
}
