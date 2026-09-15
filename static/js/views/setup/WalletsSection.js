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

// A flat section, not nested under each PersonRow — nesting would break
// test_setup.py's strict per-section locators the same way currencies/countries
// stay flat.

function WalletRow({ wallet, owner, slug, locale }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(wallet.name);
  const [error, setError] = useState(null);
  const [inUse, setInUse] = useState(null);

  async function save() {
    const err = await attempt(api.patch(`/trips/${slug}/wallets/${wallet.id}`, { name: draft }));
    if (err) return setError(err.fields?.name || null);
    setError(null);
    setRenaming(false);
    await reload('trip');
  }

  async function toggleTracked() {
    const err = await attempt(api.patch(`/trips/${slug}/wallets/${wallet.id}`, { tracked: !wallet.tracked }));
    if (err) pushFlash(errText(err, locale));
    else await reload('trip');
  }

  async function makeDefault() {
    const err = await attempt(api.patch(`/trips/${slug}/wallets/${wallet.id}`, { is_default: true }));
    if (err) pushFlash(errText(err, locale));
    else await reload('trip');
  }

  async function remove() {
    const err = await attempt(api.del(`/trips/${slug}/wallets/${wallet.id}`));
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
              <span style="cursor:pointer" onClick=${() => { setDraft(wallet.name); setRenaming(true); }}>
                <${Avatar} person=${owner} /> ${wallet.name}
              </span>
            `}
        <span class="d-flex align-items-center gap-2">
          <small class="text-body-secondary">
            ${wallet.is_default && `${t('setup.default')} · `}${wallet.tracked ? t('setup.wallet_tracked') : t('setup.wallet_untracked')}
          </small>
          <button class="btn btn-sm btn-link text-decoration-none" type="button" onClick=${toggleTracked}>
            ${wallet.tracked ? t('action.untrack') : t('action.track')}</button>
          ${!wallet.is_default && html`
            <button class="btn btn-sm btn-link text-decoration-none" type="button" onClick=${makeDefault}>
              ${t('setup.make_default')}</button>
          `}
          ${!wallet.is_default && !inUse && html`
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

export function WalletsSection({ trip, locale }) {
  const [adding, setAdding] = useState(false);
  const [personId, setPersonId] = useState(trip.people[0]?.id ?? null);
  const [name, setName] = useState('');
  const [tracked, setTracked] = useState(false);
  const [error, setError] = useState(null);

  async function add(e) {
    e.preventDefault();
    const body = { person_id: personId, name, tracked };
    const err = await attempt(api.post(`/trips/${trip.slug}/wallets`, body));
    if (err) return setError(err.fields || {});
    setName('');
    setTracked(false);
    setError(null);
    setAdding(false);
    await reload('trip');
  }

  // trip.wallets already arrives in owner sort_order then wallet sort_order
  // (API.md "Roster") - a client-side re-sort would only get it wrong for a
  // freshly created row the mock (or a real server before its next reload)
  // hands back with no sort_order of its own.
  const wallets = trip.wallets;

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t('setup.wallets')}</span>
        <${AddToggle} open=${adding} onOpen=${() => setAdding(true)} />
      </div>
      ${adding && html`
        <form class="card-body d-flex flex-wrap gap-2 align-items-start border-bottom" onSubmit=${add}>
          <select class="form-select form-select-sm" style="width:10rem" value=${personId ?? ''}
                  onChange=${(e) => setPersonId(Number(e.target.value))}>
            ${trip.people.map((p) => html`<option key=${p.id} value=${p.id}>${p.name}</option>`)}
          </select>
          <div>
            <input class="form-control form-control-sm ${error?.name ? 'is-invalid' : ''}" style="width:10rem"
                   placeholder=${t('setup.wallet_name_placeholder')} value=${name} onInput=${(e) => setName(e.target.value)} required autofocus />
            <${FieldError} error=${error?.name} locale=${locale} />
          </div>
          <div class="form-check form-switch mt-1">
            <input class="form-check-input" type="checkbox" id="new-wallet-tracked" checked=${tracked}
                   onChange=${(e) => setTracked(e.target.checked)} />
            <label class="form-check-label" for="new-wallet-tracked">${t('setup.wallet_tracked')}</label>
          </div>
          <button type="submit" class="btn btn-sm btn-primary">${t('action.save')}</button>
          <button type="button" class="btn btn-sm btn-link" onClick=${() => setAdding(false)}>${t('action.cancel')}</button>
        </form>
      `}
      <ul class="list-group list-group-flush">
        ${wallets.map((w) => html`
          <${WalletRow} key=${w.id} wallet=${w} owner=${trip.people.find((p) => p.id === w.person_id)}
                        slug=${trip.slug} locale=${locale} />
        `)}
      </ul>
      <div class="card-body pt-0"><small class="text-body-secondary">${t('setup.wallets_hint')}</small></div>
    </div>
  `;
}
