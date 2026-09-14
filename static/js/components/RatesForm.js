import { html } from '../h.js';
import { t } from '../i18n/index.js';

// `target` is whichever currency the user picked to convert everything into
// — any trip currency, not necessarily the primary. Every other currency
// needs its own typed rate into `target`. Shared by every page with a Total
// (statistics, balances): nothing here is page-specific.
export function RatesForm({ trip, target, values, onTargetChange, onRateChange }) {
  const others = trip.currencies.filter((c) => c.id !== target.id);

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('rates.your_rates')} <small class="text-body-secondary fw-normal">${t('rates.scope')}</small></div>
      <div class="card-body">
        <div class="row g-2 align-items-center mb-3">
          <div class="col-auto"><label class="col-form-label col-form-label-sm" for="rates-target">${t('rates.convert_to')}</label></div>
          <div class="col-auto">
            <select id="rates-target" class="form-select form-select-sm" value=${target.id}
                    onChange=${(e) => onTargetChange(Number(e.target.value))}>
              ${trip.currencies.map((c) => html`<option key=${c.id} value=${c.id}>${c.code}</option>`)}
            </select>
          </div>
        </div>
        ${others.map((c) => html`
          <div key=${c.id} class="row g-2 align-items-center mb-2">
            <div class="col-auto"><span class="badge text-bg-primary">1 ${c.code}</span></div>
            <div class="col-auto text-body-secondary">=</div>
            <div class="col-4 col-sm-3">
              <input class="form-control form-control-sm num text-end" inputmode="decimal"
                     value=${values[c.id] ?? ''} onChange=${(e) => onRateChange(c.id, e.target.value)} />
            </div>
            <div class="col-auto"><span class="badge text-bg-secondary">${target.code}</span></div>
          </div>
        `)}
        <div class="alert alert-primary py-2 px-3 small mt-3 mb-0">${t('rates.note')}</div>
      </div>
    </div>
  `;
}
