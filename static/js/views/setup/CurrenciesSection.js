import { useState } from 'preact/hooks';
import { html } from '../../h.js';
import { reload } from '../../store.js';
import { t } from '../../i18n/index.js';
import { api, attempt } from '../../api.js';
import { pushFlash } from '../../components/Flash.js';
import { errText } from '../../components/errText.js';
import { FieldError } from '../../components/FieldError.js';
import { AddToggle } from '../../components/AddToggle.js';

function CurrencyRow({ currency, slug, locale }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(currency.symbol || '');
  const [error, setError] = useState(null);

  async function save() {
    const err = await attempt(api.patch(`/trips/${slug}/currencies/${currency.id}`, { symbol: draft }));
    if (err) return setError(err.fields?.symbol || null);
    setError(null);
    setRenaming(false);
    await reload('trip');
  }

  async function remove() {
    const err = await attempt(api.del(`/trips/${slug}/currencies/${currency.id}`));
    if (err) pushFlash(errText(err, locale));
    else await reload('trip');
  }

  return html`
    <li class="list-group-item">
      <div class="d-flex justify-content-between align-items-center">
        <span><b>${currency.code}</b>
          ${renaming
            ? html`
                <input class="form-control form-control-sm d-inline-block ${error ? 'is-invalid' : ''}" style="width:8rem"
                       value=${draft} onInput=${(e) => setDraft(e.target.value)} autofocus />
                <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
                <button type="button" class="btn btn-sm btn-link" onClick=${() => setRenaming(false)}>${t('action.cancel')}</button>
              `
            : html`<span style="cursor:pointer" onClick=${() => { setDraft(currency.symbol || ''); setRenaming(true); }}> ${currency.symbol}</span>`}
        </span>
        <span class="d-flex align-items-center gap-2">
          ${currency.is_primary && html`<small class="text-body-secondary">${t('setup.primary')}</small>`}
          <button class="btn btn-sm btn-link link-danger text-decoration-none" type="button"
                  aria-label=${t('action.delete')} onClick=${remove}>
            <i class="bi bi-trash"></i></button>
        </span>
      </div>
      ${renaming && html`<${FieldError} error=${error} locale=${locale} />`}
    </li>
  `;
}

export function CurrenciesSection({ trip, locale }) {
  const [adding, setAdding] = useState(false);
  const [code, setCode] = useState('');
  const [symbol, setSymbol] = useState('');
  const [primary, setPrimary] = useState(false);
  const [error, setError] = useState(null);

  async function add(e) {
    e.preventDefault();
    const body = { code: code.toUpperCase() };
    if (symbol) body.symbol = symbol;
    if (primary) body.is_primary = true;
    const err = await attempt(api.post(`/trips/${trip.slug}/currencies`, body));
    if (err) return setError(err.fields || {});
    setCode('');
    setSymbol('');
    setPrimary(false);
    setError(null);
    setAdding(false);
    await reload('trip');
  }

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t('setup.currencies')}</span>
        <${AddToggle} open=${adding} onOpen=${() => setAdding(true)} />
      </div>
      ${adding && html`
        <form class="card-body d-flex flex-wrap gap-2 align-items-start border-bottom" onSubmit=${add}>
          <div>
            <input class="form-control form-control-sm text-uppercase ${error?.code ? 'is-invalid' : ''}" style="width:6rem" maxlength="3"
                   placeholder=${t('setup.currency_code_placeholder')} value=${code} onInput=${(e) => setCode(e.target.value)} required autofocus />
            <${FieldError} error=${error?.code} locale=${locale} />
          </div>
          <input class="form-control form-control-sm" style="width:10rem" placeholder=${t('setup.currency_symbol_placeholder')}
                 value=${symbol} onInput=${(e) => setSymbol(e.target.value)} />
          <div class="form-check form-switch mt-1">
            <input class="form-check-input" type="checkbox" id="new-currency-primary" checked=${primary}
                   onChange=${(e) => setPrimary(e.target.checked)} />
            <label class="form-check-label" for="new-currency-primary">${t('setup.currency_primary_label')}</label>
          </div>
          <button type="submit" class="btn btn-sm btn-primary">${t('action.save')}</button>
          <button type="button" class="btn btn-sm btn-link" onClick=${() => setAdding(false)}>${t('action.cancel')}</button>
        </form>
      `}
      <ul class="list-group list-group-flush">
        ${trip.currencies.map((c) => html`<${CurrencyRow} key=${c.id} currency=${c} slug=${trip.slug} locale=${locale} />`)}
      </ul>
    </div>
  `;
}
