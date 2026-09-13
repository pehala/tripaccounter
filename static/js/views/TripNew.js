import { useState } from 'preact/hooks';
import { html } from '../h.js';
import { api } from '../api.js';
import { t, getLocale } from '../i18n/index.js';
import { pushFlash } from '../components/Flash.js';
import { fmtParams } from '../fmt.js';

// Same six words in every locale — labels are user data, never translated
// (API.md §3 "POST /trips"). Unticking one drops it from the request body.
const STARTER_LABELS = ['food', 'lodging', 'transport', 'fun', 'groceries', 'drinks'];

function errText(err) {
  return t('err.' + err.code, fmtParams(err.params, getLocale()));
}

function Row({ children, onRemove }) {
  return html`
    <div class="d-flex gap-2 align-items-start mb-2">
      <div class="d-flex flex-wrap gap-2 flex-grow-1">${children}</div>
      <button type="button" class="btn btn-sm btn-link link-danger text-decoration-none" aria-label=${t('action.delete')} onClick=${onRemove}>
        <i class="bi bi-trash"></i></button>
    </div>
  `;
}

export function TripNew() {
  const [name, setName] = useState('');
  const [note, setNote] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [people, setPeople] = useState([{ name: '', weight: '' }]);
  const [currencies, setCurrencies] = useState([{ code: '', symbol: '', isPrimary: true }]);
  const [countries, setCountries] = useState([{ name: '', code: '' }]);
  const [labels, setLabels] = useState(() => Object.fromEntries(STARTER_LABELS.map((l) => [l, true])));
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);

  function updateRow(list, setList, index, patch) {
    setList(list.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function removeRow(list, setList, index) {
    if (list.length <= 1) return;
    setList(list.filter((_, i) => i !== index));
  }

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setFieldErrors({});
    const body = {
      name,
      people: people.filter((p) => p.name.trim()).map((p) => ({
        name: p.name.trim(),
        ...(p.weight ? { default_weight: p.weight } : {}),
      })),
      currencies: currencies
        .filter((c) => c.code.trim())
        .map((c) => ({
          code: c.code.trim().toUpperCase(),
          ...(c.symbol ? { symbol: c.symbol } : {}),
          ...(c.isPrimary ? { is_primary: true } : {}),
        })),
      countries: countries.filter((c) => c.name.trim()).map((c) => ({
        name: c.name.trim(),
        ...(c.code ? { code: c.code.trim().toUpperCase() } : {}),
      })),
      labels: STARTER_LABELS.filter((l) => labels[l]),
    };
    if (note) body.note = note;
    if (startDate) body.start_date = startDate;
    if (endDate) body.end_date = endDate;

    try {
      const res = await api.post('/trips', body);
      history.pushState(null, '', `/t/${res.trip.slug}`);
      window.dispatchEvent(new PopStateEvent('popstate'));
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) setFieldErrors(err.fields);
      else pushFlash(errText(err));
    } finally {
      setSaving(false);
    }
  }

  return html`
    <div class="container py-4" style="max-width:40rem">
      <h1 class="h4 mb-3">${t('tripnew.title')}</h1>
      <form onSubmit=${submit}>
        <div class="mb-3">
          <input class="form-control form-control-lg ${fieldErrors.name ? 'is-invalid' : ''}"
                 placeholder=${t('tripnew.name_placeholder')} value=${name}
                 onInput=${(e) => setName(e.target.value)} required autofocus />
          ${fieldErrors.name && html`<div class="invalid-feedback d-block">${errText(fieldErrors.name)}</div>`}
        </div>

        <div class="row g-3 mb-3">
          <div class="col">
            <label class="form-label small mb-1">${t('tripnew.start_date_label')}</label>
            <input type="date" class="form-control" value=${startDate} onInput=${(e) => setStartDate(e.target.value)} />
          </div>
          <div class="col">
            <label class="form-label small mb-1">${t('tripnew.end_date_label')}</label>
            <input type="date" class="form-control" value=${endDate} onInput=${(e) => setEndDate(e.target.value)} />
          </div>
        </div>

        <div class="mb-3">
          <input class="form-control" placeholder=${t('setup.note_placeholder')} value=${note}
                 onInput=${(e) => setNote(e.target.value)} />
        </div>

        <div class="card shadow-sm mb-3">
          <div class="card-header fw-semibold">${t('tripnew.people_label')}</div>
          <div class="card-body">
            ${people.map((p, i) => html`
              <${Row} key=${i} onRemove=${() => removeRow(people, setPeople, i)}>
                <input class="form-control form-control-sm" style="width:10rem" placeholder=${t('setup.person_name_placeholder')}
                       value=${p.name} onInput=${(e) => updateRow(people, setPeople, i, { name: e.target.value })} />
                <input class="form-control form-control-sm" style="width:10rem" placeholder=${t('setup.person_weight_placeholder')}
                       value=${p.weight} onInput=${(e) => updateRow(people, setPeople, i, { weight: e.target.value })} />
              <//>
            `)}
            ${fieldErrors.people && html`<div class="invalid-feedback d-block">${errText(fieldErrors.people)}</div>`}
            <button type="button" class="btn btn-sm btn-outline-primary" onClick=${() => setPeople([...people, { name: '', weight: '' }])}>${t('action.add')}</button>
          </div>
        </div>

        <div class="card shadow-sm mb-3">
          <div class="card-header fw-semibold">${t('tripnew.currencies_label')}</div>
          <div class="card-body">
            ${currencies.map((c, i) => html`
              <${Row} key=${i} onRemove=${() => removeRow(currencies, setCurrencies, i)}>
                <input class="form-control form-control-sm text-uppercase" style="width:6rem" maxlength="3" placeholder=${t('setup.currency_code_placeholder')}
                       value=${c.code} onInput=${(e) => updateRow(currencies, setCurrencies, i, { code: e.target.value })} />
                <input class="form-control form-control-sm" style="width:10rem" placeholder=${t('setup.currency_symbol_placeholder')}
                       value=${c.symbol} onInput=${(e) => updateRow(currencies, setCurrencies, i, { symbol: e.target.value })} />
                <div class="form-check form-switch mt-1">
                  <input class="form-check-input" type="checkbox" id="new-trip-currency-primary-${i}" checked=${c.isPrimary}
                         onChange=${(e) => setCurrencies(currencies.map((row, j) => ({ ...row, isPrimary: j === i && e.target.checked })))} />
                  <label class="form-check-label" for="new-trip-currency-primary-${i}">${t('setup.currency_primary_label')}</label>
                </div>
              <//>
            `)}
            ${fieldErrors.currencies && html`<div class="invalid-feedback d-block">${errText(fieldErrors.currencies)}</div>`}
            <button type="button" class="btn btn-sm btn-outline-primary" onClick=${() => setCurrencies([...currencies, { code: '', symbol: '', isPrimary: false }])}>${t('action.add')}</button>
          </div>
        </div>

        <div class="card shadow-sm mb-3">
          <div class="card-header fw-semibold">${t('tripnew.countries_label')}</div>
          <div class="card-body">
            ${countries.map((c, i) => html`
              <${Row} key=${i} onRemove=${() => removeRow(countries, setCountries, i)}>
                <input class="form-control form-control-sm" style="width:10rem" placeholder=${t('setup.country_name_placeholder')}
                       value=${c.name} onInput=${(e) => updateRow(countries, setCountries, i, { name: e.target.value })} />
                <input class="form-control form-control-sm text-uppercase" style="width:8rem" maxlength="2" placeholder=${t('setup.country_code_placeholder')}
                       value=${c.code} onInput=${(e) => updateRow(countries, setCountries, i, { code: e.target.value })} />
              <//>
            `)}
            ${fieldErrors.countries && html`<div class="invalid-feedback d-block">${errText(fieldErrors.countries)}</div>`}
            <button type="button" class="btn btn-sm btn-outline-primary" onClick=${() => setCountries([...countries, { name: '', code: '' }])}>${t('action.add')}</button>
          </div>
        </div>

        <div class="card shadow-sm mb-3">
          <div class="card-header fw-semibold">${t('tripnew.labels_label')}</div>
          <div class="card-body d-flex flex-wrap gap-2">
            ${STARTER_LABELS.map((l) => html`
              <div key=${l} class="form-check">
                <input class="form-check-input" type="checkbox" id="starter-label-${l}" checked=${labels[l]}
                       onChange=${(e) => setLabels({ ...labels, [l]: e.target.checked })} />
                <label class="form-check-label" for="starter-label-${l}">${l}</label>
              </div>
            `)}
          </div>
        </div>

        <button type="submit" class="btn btn-primary px-4" disabled=${saving}>${t('tripnew.create')}</button>
      </form>
    </div>
  `;
}
