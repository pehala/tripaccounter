import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { fmtParams } from '../fmt.js';
import { api } from '../api.js';
import { pushFlash } from '../components/Flash.js';
import { Avatar } from '../components/Avatar.js';
import { Loading } from '../components/Loading.js';

function errText(err, locale) {
  return t('err.' + err.code, fmtParams(err.params, locale));
}

// Runs a write, returns the error object on failure (or null on success) so a
// caller can decide field-level vs. flash handling without a try/catch of its own.
async function attempt(promise) {
  try {
    await promise;
    return null;
  } catch (err) {
    return err;
  }
}

function FieldError({ error, locale }) {
  if (!error) return null;
  return html`<div class="invalid-feedback d-block">${errText(error, locale)}</div>`;
}

function AddToggle({ open, onOpen }) {
  if (open) return null;
  return html`<button class="btn btn-sm btn-outline-primary" type="button" onClick=${onOpen}>${t('action.add')}</button>`;
}

// --- People -----------------------------------------------------------

function PersonRow({ person, slug, locale }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(person.name);
  const [error, setError] = useState(null);
  const [inUse, setInUse] = useState(null);

  async function save() {
    const err = await attempt(api.patch(`/trips/${slug}/people/${person.id}`, { name: draft }));
    if (err) return setError(err.fields?.name || null);
    setError(null);
    setRenaming(false);
    await reload('trip');
  }

  async function toggleActive() {
    const err = await attempt(api.patch(`/trips/${slug}/people/${person.id}`, { active: !person.active }));
    if (err) pushFlash(errText(err, locale));
    else await reload('trip');
  }

  async function remove() {
    const err = await attempt(api.del(`/trips/${slug}/people/${person.id}`));
    if (!err) return reload('trip');
    if (err.fields?.id?.code === 'in_use') setInUse(err.fields.id);
    else pushFlash(errText(err, locale));
  }

  return html`
    <li class="list-group-item">
      <div class="d-flex justify-content-between align-items-center">
        ${renaming
          ? html`
              <span class="d-inline-flex gap-1 align-items-center flex-grow-1">
                <input class="form-control form-control-sm ${error ? 'is-invalid' : ''}" style="max-width:12rem"
                       value=${draft} onInput=${(e) => setDraft(e.target.value)} autofocus />
                <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
                <button type="button" class="btn btn-sm btn-link" onClick=${() => { setRenaming(false); setError(null); }}>${t('action.cancel')}</button>
              </span>
            `
          : html`
              <span class="${person.active ? '' : 'opacity-50'}" style="cursor:pointer" onClick=${() => { setDraft(person.name); setRenaming(true); }}>
                <${Avatar} person=${person} size="lg" /> ${person.name}
                ${!person.active && html`<small class="text-body-secondary"> — ${t('setup.inactive')}</small>`}
              </span>
            `}
        <span class="d-flex align-items-center gap-2">
          <small class="text-body-secondary">${t('setup.share', { weight: person.default_weight })}</small>
          <button class="btn btn-sm btn-link text-decoration-none" type="button" onClick=${toggleActive}>
            ${person.active ? t('action.deactivate') : t('action.activate')}</button>
          ${!inUse && html`
            <button class="btn btn-sm btn-link link-danger text-decoration-none" type="button"
                    aria-label=${t('action.delete')} onClick=${remove}>
              <i class="bi bi-trash"></i></button>
          `}
        </span>
      </div>
      ${renaming && html`<${FieldError} error=${error} locale=${locale} />`}
      ${inUse && html`<div class="alert alert-warning py-1 px-2 small mt-2 mb-0">${errText({ code: 'in_use', params: inUse.params }, locale)}</div>`}
    </li>
  `;
}

function PeopleSection({ trip, locale }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [weight, setWeight] = useState('');
  const [error, setError] = useState(null);

  async function add(e) {
    e.preventDefault();
    const body = { name };
    if (weight) body.default_weight = weight;
    const err = await attempt(api.post(`/trips/${trip.slug}/people`, body));
    if (err) return setError(err.fields || {});
    setName('');
    setWeight('');
    setError(null);
    setAdding(false);
    await reload('trip');
  }

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t('setup.people')}</span>
        <${AddToggle} open=${adding} onOpen=${() => setAdding(true)} />
      </div>
      ${adding && html`
        <form class="card-body d-flex flex-wrap gap-2 align-items-start border-bottom" onSubmit=${add}>
          <div>
            <input class="form-control form-control-sm ${error?.name ? 'is-invalid' : ''}" style="width:10rem"
                   placeholder=${t('setup.person_name_placeholder')} value=${name} onInput=${(e) => setName(e.target.value)} required autofocus />
            <${FieldError} error=${error?.name} locale=${locale} />
          </div>
          <input class="form-control form-control-sm" style="width:10rem" placeholder=${t('setup.person_weight_placeholder')}
                 value=${weight} onInput=${(e) => setWeight(e.target.value)} />
          <button type="submit" class="btn btn-sm btn-primary">${t('action.save')}</button>
          <button type="button" class="btn btn-sm btn-link" onClick=${() => setAdding(false)}>${t('action.cancel')}</button>
        </form>
      `}
      <ul class="list-group list-group-flush">
        ${trip.people.map((p) => html`<${PersonRow} key=${p.id} person=${p} slug=${trip.slug} locale=${locale} />`)}
      </ul>
    </div>
  `;
}

// --- Currencies ---------------------------------------------------------

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

function CurrenciesSection({ trip, locale }) {
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

// --- Countries ------------------------------------------------------------

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

function CountriesSection({ trip, locale }) {
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

// --- Labels -----------------------------------------------------------

function LabelChip({ label, slug, locale }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(label.name);

  async function save() {
    const err = await attempt(api.patch(`/trips/${slug}/labels/${label.id}`, { name: draft }));
    if (err) pushFlash(errText(err, locale));
    setRenaming(false);
    await reload('labels');
  }

  async function remove() {
    const err = await attempt(api.del(`/trips/${slug}/labels/${label.id}`));
    if (err) pushFlash(errText(err, locale));
    else await reload('labels');
  }

  if (renaming) {
    return html`
      <span class="d-inline-flex gap-1 align-items-center">
        <input class="form-control form-control-sm" style="width:8rem" value=${draft}
               onInput=${(e) => setDraft(e.target.value)} autofocus />
        <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
        <button type="button" class="btn btn-sm btn-link" onClick=${() => setRenaming(false)}>${t('action.cancel')}</button>
      </span>
    `;
  }

  return html`
    <span class="badge rounded-pill text-bg-light border d-inline-flex align-items-center gap-1 ${label.use_count === 0 ? 'opacity-50' : ''}">
      <span style="cursor:pointer" onClick=${() => { setDraft(label.name); setRenaming(true); }}>${label.name}</span>
      <small class="text-body-secondary">${label.use_count}</small>
      <button type="button" class="btn-close" style="font-size:.5rem" aria-label=${t('action.remove')} onClick=${remove}></button>
    </span>
  `;
}

function LabelsSection({ trip, labels, locale }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState(null);

  async function add(e) {
    e.preventDefault();
    const err = await attempt(api.post(`/trips/${trip.slug}/labels`, { name }));
    if (err) return setError(err.fields?.name || null);
    setName('');
    setError(null);
    setAdding(false);
    await reload('labels');
  }

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t('setup.labels')}</span>
        <${AddToggle} open=${adding} onOpen=${() => setAdding(true)} />
      </div>
      ${adding && html`
        <form class="card-body d-flex flex-wrap gap-2 align-items-start border-bottom" onSubmit=${add}>
          <div>
            <input class="form-control form-control-sm ${error ? 'is-invalid' : ''}" style="width:10rem"
                   placeholder=${t('setup.label_name_placeholder')} value=${name} onInput=${(e) => setName(e.target.value)} required autofocus />
            <${FieldError} error=${error} locale=${locale} />
          </div>
          <button type="submit" class="btn btn-sm btn-primary">${t('action.save')}</button>
          <button type="button" class="btn btn-sm btn-link" onClick=${() => setAdding(false)}>${t('action.cancel')}</button>
        </form>
      `}
      <div class="card-body d-flex flex-wrap gap-1">
        ${labels.map((l) => html`<${LabelChip} key=${l.id} label=${l} slug=${trip.slug} locale=${locale} />`)}
      </div>
      <div class="card-body pt-0"><small class="text-body-secondary">${t('setup.labels_hint')}</small></div>
    </div>
  `;
}

// --- Trip -----------------------------------------------------------------

function TripSection({ trip, locale }) {
  const [field, setField] = useState(null); // 'name' | 'note' | null
  const [draft, setDraft] = useState('');
  const [error, setError] = useState(null);

  function start(name, value) {
    setField(name);
    setDraft(value || '');
    setError(null);
  }

  async function save() {
    const err = await attempt(api.patch(`/trips/${trip.slug}`, { [field]: draft }));
    if (err) return setError(err.fields?.[field] || null);
    setField(null);
    await reload('trip');
  }

  async function archive() {
    if (!window.confirm(t('setup.archive_confirm'))) return;
    const err = await attempt(api.patch(`/trips/${trip.slug}`, { archived: true }));
    if (err) pushFlash(errText(err, locale));
    else await reload('trip');
  }

  return html`
    <div class="card shadow-sm">
      <div class="card-header fw-semibold">${t('setup.trip')} ${trip.archived && html`<span class="badge text-bg-secondary">${t('setup.archived_badge')}</span>`}</div>
      <ul class="list-group list-group-flush">
        <li class="list-group-item">
          <div class="d-flex justify-content-between align-items-center">
            <span>${t('setup.name_label')}</span>
            ${field === 'name'
              ? html`
                  <span class="d-inline-flex gap-1 align-items-center">
                    <input class="form-control form-control-sm ${error ? 'is-invalid' : ''}" value=${draft}
                           onInput=${(e) => setDraft(e.target.value)} autofocus />
                    <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
                    <button type="button" class="btn btn-sm btn-link" onClick=${() => setField(null)}>${t('action.cancel')}</button>
                  </span>
                `
              : html`<span style="cursor:pointer" onClick=${() => start('name', trip.name)}>${trip.name}</span>`}
          </div>
          ${field === 'name' && html`<${FieldError} error=${error} locale=${locale} />`}
        </li>
        <li class="list-group-item">
          <div class="d-flex justify-content-between align-items-center">
            <span>${t('setup.note_label')}</span>
            ${field === 'note'
              ? html`
                  <span class="d-inline-flex gap-1 align-items-center">
                    <input class="form-control form-control-sm" value=${draft} placeholder=${t('setup.note_placeholder')}
                           onInput=${(e) => setDraft(e.target.value)} autofocus />
                    <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
                    <button type="button" class="btn btn-sm btn-link" onClick=${() => setField(null)}>${t('action.cancel')}</button>
                  </span>
                `
              : html`<span class="text-body-secondary" style="cursor:pointer" onClick=${() => start('note', trip.note)}>${trip.note || t('setup.note_placeholder')}</span>`}
          </div>
        </li>
        <li class="list-group-item d-flex justify-content-between">
          <span>${t('setup.link')} <small class="text-body-secondary">${t('setup.link_note')}</small></span><code>/t/${trip.slug}</code>
        </li>
        <li class="list-group-item d-flex justify-content-between">
          <span>${t('setup.export')}</span>
          <span>
            <a href="/api/v1/trips/${trip.slug}/export?format=csv">${t('setup.export_csv')}</a> ·
            <a href="/api/v1/trips/${trip.slug}/export?format=json">${t('setup.export_json')}</a>
          </span>
        </li>
        ${!trip.archived && html`
          <li class="list-group-item">
            <a href="#" class="link-danger" onClick=${(e) => { e.preventDefault(); archive(); }}>${t('setup.archive')}</a>
          </li>
        `}
      </ul>
    </div>
  `;
}

export function Setup() {
  const store = useStore();
  const locale = getLocale();

  useEffect(() => {
    if (!store.labels) reload('labels');
  }, [store.slug]);

  if (!store.labels) return html`<${Loading} />`;

  const trip = store.trip;

  return html`
    <${PeopleSection} trip=${trip} locale=${locale} />
    <${CurrenciesSection} trip=${trip} locale=${locale} />
    <${CountriesSection} trip=${trip} locale=${locale} />
    <${LabelsSection} trip=${trip} labels=${store.labels} locale=${locale} />
    <${TripSection} trip=${trip} locale=${locale} />
  `;
}
