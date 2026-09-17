import { useState } from 'preact/hooks';
import { html } from '../../h.js';
import { reload } from '../../store.js';
import { t } from '../../i18n/index.js';
import { api, attempt } from '../../api.js';
import { pushFlash } from '../../components/Flash.js';
import { errText } from '../../components/errText.js';
import { FieldError } from '../../components/FieldError.js';
import { AddToggle } from '../../components/AddToggle.js';

function CountryRow({ country, slug, locale }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(country.name);
  const [error, setError] = useState(null);

  async function save() {
    const err = await attempt(api.patch(`/trips/${slug}/countries/${country.id}`, { name: draft }));
    if (err) return setError(err.fields?.name || null);
    setError(null);
    setRenaming(false);
    await reload('trip');
  }

  async function remove() {
    const err = await attempt(api.del(`/trips/${slug}/countries/${country.id}`));
    if (err) pushFlash(errText(err, locale));
    else await reload('trip');
  }

  return html`
    <li class="list-group-item">
      <div class="d-flex justify-content-between align-items-center">
        ${renaming
          ? html`
              <span class="d-inline-flex gap-1 align-items-center">
                <input class="form-control form-control-sm ${error ? 'is-invalid' : ''}" style="width:10rem"
                       value=${draft} onInput=${(e) => setDraft(e.target.value)} autofocus />
                <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
                <button type="button" class="btn btn-sm btn-link" onClick=${() => setRenaming(false)}>${t('action.cancel')}</button>
              </span>
            `
          : html`<span style="cursor:pointer" onClick=${() => { setDraft(country.name); setRenaming(true); }}>${country.flag} ${country.name}</span>`}
        <span class="d-flex align-items-center gap-2">
          <small class="text-body-secondary">
            ${country.is_default && `${t('setup.default')} · `}${t('setup.item_count', { n: country.item_count })}
          </small>
          <button class="btn btn-sm btn-link link-danger text-decoration-none" type="button"
                  aria-label=${t('action.delete')} onClick=${remove}>
            <i class="bi bi-trash"></i></button>
        </span>
      </div>
      ${renaming && html`<${FieldError} error=${error} locale=${locale} />`}
    </li>
  `;
}

export function CountriesSection({ trip, locale }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState(null);

  async function add(e) {
    e.preventDefault();
    const body = { name };
    if (code) body.code = code.toUpperCase();
    const err = await attempt(api.post(`/trips/${trip.slug}/countries`, body));
    if (err) return setError(err.fields || {});
    setName('');
    setCode('');
    setError(null);
    setAdding(false);
    await reload('trip');
  }

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t('setup.countries')}</span>
        <${AddToggle} open=${adding} onOpen=${() => setAdding(true)} />
      </div>
      ${adding && html`
        <form class="card-body d-flex flex-wrap gap-2 align-items-start border-bottom" onSubmit=${add}>
          <div>
            <input class="form-control form-control-sm ${error?.name ? 'is-invalid' : ''}" style="width:10rem"
                   placeholder=${t('setup.country_name_placeholder')} value=${name} onInput=${(e) => setName(e.target.value)} required autofocus />
            <${FieldError} error=${error?.name} locale=${locale} />
          </div>
          <input class="form-control form-control-sm text-uppercase" style="width:8rem" maxlength="2"
                 placeholder=${t('setup.country_code_placeholder')} value=${code} onInput=${(e) => setCode(e.target.value)} />
          <button type="submit" class="btn btn-sm btn-primary">${t('action.save')}</button>
          <button type="button" class="btn btn-sm btn-link" onClick=${() => setAdding(false)}>${t('action.cancel')}</button>
        </form>
      `}
      <ul class="list-group list-group-flush">
        ${trip.countries.map((c) => html`<${CountryRow} key=${c.id} country=${c} slug=${trip.slug} locale=${locale} />`)}
      </ul>
      <div class="card-body pt-0"><small class="text-body-secondary">${t('setup.countries_hint')}</small></div>
    </div>
  `;
}
