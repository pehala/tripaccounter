import { useState } from 'preact/hooks';
import { html } from '../h.js';
import { reload } from '../store.js';
import { t } from '../i18n/index.js';
import { api, attempt } from '../api.js';
import { routeError } from './errText.js';
import { FieldError } from './FieldError.js';
import { RatesForm } from './RatesForm.js';
import { SettledBadge } from './SettledBadge.js';

// The Total's rate form plus settle / unlock, shared by balances and statistics.
export function TotalRatesPanel({ trip, rates, locale }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function write(confirmKey, request) {
    if (!window.confirm(t(confirmKey, { code: rates.target.code }))) return;
    setBusy(true);
    setError(null);
    const err = await attempt(request());
    setBusy(false);
    if (err) setError(Object.values(routeError(err, locale))[0] ?? null);
    else await reload('trip');
  }

  const settle = () => write('settlement.settle_confirm',
    () => api.put(`/trips/${trip.slug}/settlement`, rates.settlementBody()));
  const unlock = () => write('settlement.unlock_confirm',
    () => api.del(`/trips/${trip.slug}/settlement`));

  return html`
    <${RatesForm} trip=${trip} target=${rates.target} values=${rates.values} readOnly=${Boolean(rates.settlement)}
                  onTargetChange=${rates.onTargetChange} onRateChange=${rates.onRateChange}>
      ${(rates.settlement || rates.settleable) && html`<div class="d-flex flex-wrap align-items-center gap-2 mt-3 settlement-controls">
        ${rates.settlement && html`
          <${SettledBadge} settlement=${rates.settlement} locale=${locale} />
          <button type="button" class="btn btn-sm btn-outline-secondary" disabled=${busy} onClick=${unlock}>
            <i class="bi bi-unlock"></i> ${t('settlement.unlock')}</button>
        `}
        ${!rates.settlement && rates.settleable && html`
          <button type="button" class="btn btn-sm btn-success" disabled=${busy} onClick=${settle}>
            <i class="bi bi-lock"></i> ${t('settlement.settle')}</button>
        `}
      </div>`}
      <${FieldError} error=${error} locale=${locale} />
    <//>
    ${!rates.ready && html`<div class="alert alert-secondary py-2 px-3 small mb-0">${t('rates.missing')}</div>`}
    ${rates.ready && html`<div class="small text-body-secondary mb-2">${t('rates.total_note')}</div>`}
  `;
}
