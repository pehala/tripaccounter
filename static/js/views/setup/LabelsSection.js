import { useState } from 'preact/hooks';
import { html } from '../../h.js';
import { reload } from '../../store.js';
import { t } from '../../i18n/index.js';
import { api, attempt } from '../../api.js';
import { pushFlash } from '../../components/Flash.js';
import { errText } from '../../components/errText.js';
import { FieldError } from '../../components/FieldError.js';
import { AddToggle } from '../../components/AddToggle.js';

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
    <span class="badge rounded-pill bg-body-secondary text-body border d-inline-flex align-items-center gap-1 ${label.use_count === 0 ? 'opacity-50' : ''}">
      <span style="cursor:pointer" onClick=${() => { setDraft(label.name); setRenaming(true); }}>${label.name}</span>
      <small class="text-body-secondary">${label.use_count}</small>
      <button type="button" class="btn-close" style="font-size:.5rem" aria-label=${t('action.remove')} onClick=${remove}></button>
    </span>
  `;
}

export function LabelsSection({ trip, labels, locale }) {
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
