import { useState } from 'preact/hooks';
import { html } from '../../h.js';
import { reload } from '../../store.js';
import { t } from '../../i18n/index.js';
import { dateRange } from '../../fmt.js';
import { api, attempt } from '../../api.js';
import { pushFlash } from '../../components/Flash.js';
import { errText } from '../../components/errText.js';
import { FieldError } from '../../components/FieldError.js';

export function TripSection({ trip, locale }) {
  const [field, setField] = useState(null); // 'name' | 'note' | 'dates' | null
  const [draft, setDraft] = useState('');
  const [draftStart, setDraftStart] = useState('');
  const [draftEnd, setDraftEnd] = useState('');
  const [error, setError] = useState(null);

  function start(name, value) {
    setField(name);
    setDraft(value || '');
    setError(null);
  }

  function startDates() {
    setField('dates');
    setDraftStart(trip.start_date || '');
    setDraftEnd(trip.end_date || '');
    setError(null);
  }

  async function save() {
    const body = field === 'dates'
      ? { start_date: draftStart || null, end_date: draftEnd || null }
      : { [field]: draft };
    const err = await attempt(api.patch(`/trips/${trip.slug}`, body));
    if (err) return setError(err.fields?.start_date || err.fields?.end_date || err.fields?.[field] || null);
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
        <li class="list-group-item">
          <div class="d-flex justify-content-between align-items-center">
            <span>${t('setup.dates_label')}</span>
            ${field === 'dates'
              ? html`
                  <span class="d-inline-flex gap-1 align-items-center">
                    <input type="date" class="form-control form-control-sm" value=${draftStart}
                           onInput=${(e) => setDraftStart(e.target.value)} autofocus />
                    <input type="date" class="form-control form-control-sm" value=${draftEnd}
                           onInput=${(e) => setDraftEnd(e.target.value)} />
                    <button type="button" class="btn btn-sm btn-primary" onClick=${save}>${t('action.save')}</button>
                    <button type="button" class="btn btn-sm btn-link" onClick=${() => setField(null)}>${t('action.cancel')}</button>
                  </span>
                `
              : html`<span class="text-body-secondary" style="cursor:pointer" onClick=${startDates}>${dateRange(trip.start_date, trip.end_date, locale) || t('setup.dates_placeholder')}</span>`}
          </div>
          ${field === 'dates' && html`<${FieldError} error=${error} locale=${locale} />`}
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
