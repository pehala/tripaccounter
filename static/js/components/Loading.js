import { html } from '../h.js';
import { t } from '../i18n/index.js';

// One loading treatment everywhere a store field isn't ready yet — trip, tab
// data, trip list — so a full page load never swaps between differently
// shaped placeholders on its way to real content.
export function Loading() {
  return html`
    <div class="d-flex justify-content-center py-5">
      <div class="spinner-border text-secondary" role="status">
        <span class="visually-hidden">${t('app.loading')}</span>
      </div>
    </div>
  `;
}
