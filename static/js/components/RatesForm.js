import { useEffect } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { rate } from '../fmt.js';
import { rateBetween } from '../convert.js';
import { Loading } from './Loading.js';

// `target` is whichever currency the user picked to convert everything into
// — any trip currency, not necessarily the primary. Every other currency
// needs its own typed rate into `target`. Shared by every page with a Total
// (statistics, balances): nothing here is page-specific. Each person's average
// exchange rate for a pair is offered as a link that fills the input.
export function RatesForm({ trip, target, values, onTargetChange, onRateChange }) {
  const store = useStore();
  const locale = getLocale();
  const others = trip.currencies.filter((c) => c.id !== target.id);

  useEffect(() => {
    if (!store.exchangeRates) reload('exchangeRates');
  }, [store.slug]);

  // Rendered only once the rates are in: a re-render when they arrive would
  // reset an input the user is typing in before its change event fires.
  if (!store.exchangeRates) return html`<${Loading} />`;

  function averages(currency) {
    return store.exchangeRates.flatMap((row) => {
      const value = rateBetween(row, currency.code, target.code);
      const person = trip.people.find((p) => p.id === row.person_id);
      return value === null || !person ? [] : [{ person, text: rate(value, locale) }];
    });
  }

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
            ${averages(c).map(({ person, text }) => html`
              <div key=${person.id} class="col-auto">
                <button type="button" class="btn btn-outline-secondary btn-sm rate-average" title=${t('rates.use_average')}
                        onClick=${() => onRateChange(c.id, text)}>${person.name} ${text}</button>
              </div>
            `)}
          </div>
        `)}
        <div class="alert alert-primary py-2 px-3 small mt-3 mb-0">${t('rates.note')}</div>
      </div>
    </div>
  `;
}
