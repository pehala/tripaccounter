import { useState } from 'preact/hooks';
import { html } from '../../h.js';
import { reload } from '../../store.js';
import { t } from '../../i18n/index.js';
import { api, attempt } from '../../api.js';
import { pushFlash } from '../../components/Flash.js';
import { Avatar } from '../../components/Avatar.js';
import { errText } from '../../components/errText.js';
import { FieldError } from '../../components/FieldError.js';
import { AddToggle } from '../../components/AddToggle.js';

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

export function PeopleSection({ trip, locale }) {
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
