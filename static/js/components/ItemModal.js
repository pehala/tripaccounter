import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { html } from '../h.js';
import { api } from '../api.js';
import { reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { parse, money, fmtParams, toInputValue, fromInputValue } from '../fmt.js';
import { pushFlash } from './Flash.js';
import { PersonChip } from './PersonChip.js';
import { LabelInput } from './LabelInput.js';
import { SplitEditor } from './SplitEditor.js';

function initialState(item, trip) {
  if (item) {
    const included = new Set(item.split.shares.filter((s) => s.weight !== null).map((s) => s.person_id));
    const weights = {};
    const exacts = {};
    for (const s of item.split.shares) {
      if (s.weight === null) continue;
      if (item.split.mode === 'exact') exacts[s.person_id] = String(s.owed ?? '');
      else weights[s.person_id] = s.weight;
    }
    return {
      name: item.name,
      amount: String(item.amount),
      currencyId: item.currency_id,
      payerId: item.payer_id,
      countryId: item.country_id,
      occurredAt: toInputValue(item.occurred_at),
      labels: [...item.labels],
      mapUrl: item.map_url ?? '',
      lat: item.lat ?? '',
      lon: item.lon ?? '',
      splitMode: item.split.mode,
      included,
      weights,
      exacts,
      preview: item.split,
    };
  }
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const defaultCountry = trip.countries.find((c) => c.is_default) || trip.countries[0];
  return {
    name: '',
    amount: '',
    currencyId: primary?.id ?? null,
    payerId: trip.people.find((p) => p.active)?.id ?? null,
    countryId: defaultCountry?.id ?? null,
    occurredAt: toInputValue(new Date().toISOString()),
    labels: [],
    mapUrl: '',
    lat: '',
    lon: '',
    splitMode: 'equal',
    included: new Set(trip.people.filter((p) => p.active).map((p) => p.id)),
    weights: {},
    exacts: {},
    preview: null,
  };
}

export function ItemModal({ trip, labels, item, onClose }) {
  const locale = getLocale();
  const modalRef = useRef(null);
  const bsRef = useRef(null);
  const isEdit = Boolean(item);
  const activePeople = useMemo(() => trip.people.filter((p) => p.active), [trip]);

  const [state, setState] = useState(() => initialState(item, trip));
  const [fieldErrors, setFieldErrors] = useState({});
  const [previewFailed, setPreviewFailed] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const el = modalRef.current;
    bsRef.current = window.bootstrap.Modal.getOrCreateInstance(el);
    bsRef.current.show();
    const onHidden = () => onClose();
    el.addEventListener('hidden.bs.modal', onHidden);
    return () => {
      el.removeEventListener('hidden.bs.modal', onHidden);
      bsRef.current.hide();
    };
  }, []);

  function set(patch) { setState((s) => ({ ...s, ...patch })); }

  function splitBody() {
    const people = [...state.included].map((id) => ({ id }));
    if (state.splitMode === 'shares') {
      return people.map(({ id }) => ({ person_id: id, weight: state.weights[id] || '1' }));
    }
    if (state.splitMode === 'exact') {
      return people.map(({ id }) => ({ person_id: id, amount: state.exacts[id] || '0' }));
    }
    return people.map(({ id }) => ({ person_id: id }));
  }

  async function firePreview(overrides = {}) {
    const amount = parse(overrides.amount ?? state.amount, locale);
    if (!amount) return;
    const body = {
      amount,
      currency_id: overrides.currencyId ?? state.currencyId,
      split_mode: overrides.splitMode ?? state.splitMode,
      shares: overrides.shares ?? splitBody(),
    };
    try {
      const res = await api.post(`/trips/${trip.slug}/items/preview-split`, body);
      setState((s) => ({ ...s, preview: res.split }));
      setPreviewFailed(false);
      setPreviewError(null);
    } catch (err) {
      setPreviewFailed(true);
      setPreviewError(err.fields?.shares ? err.fields.shares : null);
    }
  }

  function toggleIncluded(personId) {
    const included = new Set(state.included);
    if (included.has(personId)) included.delete(personId);
    else included.add(personId);
    set({ included });
    firePreview({ shares: buildSharesFor(state.splitMode, included, state.weights, state.exacts) });
  }

  function buildSharesFor(mode, included, weights, exacts) {
    const ids = [...included];
    if (mode === 'shares') return ids.map((id) => ({ person_id: id, weight: weights[id] || '1' }));
    if (mode === 'exact') return ids.map((id) => ({ person_id: id, amount: exacts[id] || '0' }));
    return ids.map((id) => ({ person_id: id }));
  }

  function changeMode(mode) {
    set({ splitMode: mode });
    firePreview({ splitMode: mode, shares: buildSharesFor(mode, state.included, state.weights, state.exacts) });
  }

  function changeWeight(personId, value, commit) {
    const weights = { ...state.weights, [personId]: value };
    set({ weights });
    if (commit) firePreview({ shares: buildSharesFor('shares', state.included, weights, state.exacts) });
  }

  function changeExact(personId, value, commit) {
    const exacts = { ...state.exacts, [personId]: value };
    set({ exacts });
    if (commit) firePreview({ shares: buildSharesFor('exact', state.included, state.weights, exacts) });
  }

  function amountChanged(e) {
    const raw = e.target.value;
    set({ amount: raw });
    firePreview({ amount: raw });
  }

  function currencyChanged(e) {
    const currencyId = Number(e.target.value);
    set({ currencyId });
    firePreview({ currencyId });
  }

  function buildBody() {
    const amount = parse(state.amount, locale);
    return {
      name: state.name.trim(),
      amount,
      currency_id: state.currencyId,
      payer_id: state.payerId,
      country_id: state.countryId,
      occurred_at: fromInputValue(state.occurredAt),
      labels: state.labels,
      map_url: state.mapUrl.trim() || null,
      lat: state.lat === '' ? null : state.lat,
      lon: state.lon === '' ? null : state.lon,
      split_mode: state.splitMode,
      shares: splitBody(),
    };
  }

  async function save(e, again) {
    e.preventDefault();
    const form = e.target.closest('form');
    if (form && !form.reportValidity()) return;
    setSaving(true);
    setFieldErrors({});
    const body = buildBody();
    const hadNewLabel = state.labels.some((name) => !labels.some((l) => l.name.toLowerCase() === name));
    try {
      if (isEdit) await api.patch(`/trips/${trip.slug}/items/${item.id}`, body);
      else await api.post(`/trips/${trip.slug}/items`, body);
      await reload('items');
      if (hadNewLabel) await reload('labels');
      if (again && !isEdit) {
        set({ name: '', amount: '', labels: [], preview: null });
      } else {
        onClose();
      }
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) {
        setFieldErrors(err.fields);
      } else {
        pushFlash(t('err.' + err.code, fmtParams(err.params, locale)));
      }
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(t('item.delete_confirm'))) return;
    try {
      await api.del(`/trips/${trip.slug}/items/${item.id}`);
      await reload('items');
      onClose();
    } catch (err) {
      pushFlash(t('err.' + err.code, fmtParams(err.params, locale)));
    }
  }

  function fieldError(name) {
    const err = fieldErrors[name];
    if (!err) return null;
    return html`<div class="invalid-feedback d-block">${t('err.' + err.code, fmtParams(err.params, locale))}</div>`;
  }

  return html`
    <div class="modal fade" ref=${modalRef} tabindex="-1">
      <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-fullscreen-sm-down">
        <form class="modal-content" onSubmit=${(e) => save(e, false)}>
          <div class="modal-header py-2 ${isEdit ? 'bg-warning-subtle border-warning-subtle' : ''}">
            <h2 class="modal-title h6 mb-0 d-flex align-items-center gap-2">
              <i class="bi ${isEdit ? 'bi-pencil' : 'bi-plus-circle'}"></i>
              ${isEdit ? t('item.edit_title') : t('item.new_title')}
            </h2>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label=${t('action.close')}></button>
          </div>

          <div class="modal-body">
            <div class="mb-3">
              <input class="form-control form-control-lg ${fieldErrors.name ? 'is-invalid' : ''}" name="name"
                     placeholder=${t('item.name_placeholder')} autocomplete="off" required autofocus
                     value=${state.name} onInput=${(e) => set({ name: e.target.value })} />
              ${fieldError('name')}
            </div>

            <div class="input-group input-group-lg mb-3">
              <input class="form-control num text-end fw-semibold ${fieldErrors.amount ? 'is-invalid' : ''}" name="amount"
                     inputmode="decimal" placeholder="0" required
                     value=${state.amount} onInput=${(e) => set({ amount: e.target.value })} onChange=${amountChanged} />
              <select class="form-select flex-grow-0 w-auto" name="currency_id" value=${state.currencyId} onChange=${currencyChanged}>
                ${trip.currencies.map((c) => html`<option key=${c.id} value=${c.id}>${c.code}</option>`)}
              </select>
              ${fieldError('amount')}
            </div>

            <label class="form-label small mb-1">${t('item.country_label')} <span class="text-danger">*</span></label>
            <select class="form-select mb-3 ${fieldErrors.country_id ? 'is-invalid' : ''}" name="country_id" required
                    value=${state.countryId ?? ''} onChange=${(e) => set({ countryId: Number(e.target.value) })}>
              ${trip.countries.map((c) => html`<option key=${c.id} value=${c.id}>${c.flag} ${c.name}</option>`)}
            </select>
            ${fieldError('country_id')}

            <label class="form-label small mb-1">${t('item.paid_by_label')}</label>
            <div class="who d-flex gap-1 flex-wrap mb-3">
              ${activePeople.map((p) => html`
                <${PersonChip} key=${p.id} person=${p} type="radio" name="payer_id" id="pay-${p.id}"
                                checked=${state.payerId === p.id} onChange=${() => set({ payerId: p.id })} />
              `)}
            </div>

            <${SplitEditor} people=${activePeople} mode=${state.splitMode} onModeChange=${changeMode}
                            included=${state.included} onToggle=${toggleIncluded}
                            weights=${state.weights} onWeightChange=${changeWeight}
                            exacts=${state.exacts} onExactChange=${changeExact}
                            preview=${state.preview} previewFailed=${previewFailed} previewError=${previewError}
                            locale=${locale} />
            ${fieldError('shares')}

            <div class="row g-3 mt-0">
              <div class="col-12 col-sm-6">
                <label class="form-label small mb-1">${t('item.when_label')}</label>
                <input type="datetime-local" class="form-control ${fieldErrors.occurred_at ? 'is-invalid' : ''}"
                       value=${state.occurredAt} onChange=${(e) => set({ occurredAt: e.target.value })} />
                ${fieldError('occurred_at')}
              </div>
              <div class="col-12 col-sm-6">
                <label class="form-label small mb-1">${t('item.labels_label')}</label>
                <${LabelInput} value=${state.labels} onChange=${(v) => set({ labels: v })}
                               suggestions=${labels.map((l) => l.name)} listId="trip-labels" />
                <div class="form-text">${t('item.labels_hint')}</div>
              </div>
              <div class="col-12">
                <label class="form-label small mb-1">${t('item.location_label')}
                  <span class="text-body-secondary">${t('item.location_optional')}</span></label>
                <div class="input-group mb-2">
                  <span class="input-group-text"><i class="bi bi-geo-alt"></i></span>
                  <input class="form-control ${fieldErrors.map_url ? 'is-invalid' : ''}"
                         placeholder=${t('item.location_map_placeholder')}
                         value=${state.mapUrl} onInput=${(e) => set({ mapUrl: e.target.value })} />
                </div>
                ${fieldError('map_url')}
                <div class="input-group">
                  <input class="form-control num ${fieldErrors.lat ? 'is-invalid' : ''}" inputmode="decimal"
                         placeholder=${t('item.location_lat_placeholder')}
                         value=${state.lat} onInput=${(e) => set({ lat: e.target.value })} />
                  <input class="form-control num ${fieldErrors.lon ? 'is-invalid' : ''}" inputmode="decimal"
                         placeholder=${t('item.location_lon_placeholder')}
                         value=${state.lon} onInput=${(e) => set({ lon: e.target.value })} />
                </div>
                ${fieldError('lat')}${fieldError('lon')}
              </div>
            </div>
          </div>

          <div class="modal-footer py-2">
            ${isEdit && html`
              <button type="button" class="btn btn-link link-danger text-decoration-none me-auto" onClick=${remove}>
                <i class="bi bi-trash"></i> ${t('item.delete')}</button>
            `}
            ${!isEdit && html`
              <button type="button" class="btn btn-link link-secondary text-decoration-none me-auto d-none d-sm-inline"
                      data-bs-dismiss="modal">${t('item.cancel')}</button>
            `}
            ${!isEdit && html`
              <button type="button" class="btn btn-outline-primary" disabled=${saving}
                      onClick=${(e) => save(e, true)}>${t('item.save_another')}</button>
            `}
            <button type="submit" class="btn btn-primary px-4" disabled=${saving}>${t('item.save')}</button>
          </div>
        </form>
      </div>
    </div>
  `;
}
