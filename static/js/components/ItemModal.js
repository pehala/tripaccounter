import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { html } from '../h.js';
import { api } from '../api.js';
import { reload, invalidateMoneyViews } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { parse, money, fmtParams, toInputValue, fromInputValue } from '../fmt.js';
import { pushFlash } from './Flash.js';
import { PersonChip } from './PersonChip.js';
import { LabelInput } from './LabelInput.js';
import { SplitEditor } from './SplitEditor.js';
import { TransferFields } from './TransferFields.js';

function walletsFor(trip, personId) {
  return (trip.wallets || []).filter((w) => w.person_id === personId);
}

function defaultWalletFor(trip, personId) {
  return walletsFor(trip, personId).find((w) => w.is_default);
}

function initialItemState(item, trip) {
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
      walletId: item.wallet_id,
      countryId: item.country_id,
      occurredAt: toInputValue(item.occurred_at),
      labels: [...item.labels],
      city: item.city ?? '',
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
  const payerId = trip.people.find((p) => p.active)?.id ?? null;
  return {
    name: '',
    amount: '',
    currencyId: primary?.id ?? null,
    payerId,
    walletId: defaultWalletFor(trip, payerId)?.id ?? null,
    countryId: defaultCountry?.id ?? null,
    occurredAt: toInputValue(new Date().toISOString()),
    labels: [],
    city: '',
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

function initialTransferState(transfer, trip) {
  if (transfer) {
    return {
      fromWalletId: transfer.from_wallet_id,
      fromAmount: String(transfer.from_amount),
      fromCurrencyId: transfer.from_currency_id,
      toWalletId: transfer.to_wallet_id,
      toAmount: String(transfer.to_amount),
      toCurrencyId: transfer.to_currency_id,
      toEdited: transfer.to_currency_id !== transfer.from_currency_id || transfer.to_amount !== transfer.from_amount,
      occurredAt: toInputValue(transfer.occurred_at),
      note: transfer.note ?? '',
    };
  }
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const firstWallet = (trip.wallets || [])[0];
  return {
    fromWalletId: firstWallet?.id ?? null,
    fromAmount: '',
    fromCurrencyId: primary?.id ?? null,
    toWalletId: null,
    toAmount: '',
    toCurrencyId: primary?.id ?? null,
    toEdited: false,
    occurredAt: toInputValue(new Date().toISOString()),
    note: '',
  };
}

export function ItemModal({ trip, labels, entry, onClose }) {
  const locale = getLocale();
  const modalRef = useRef(null);
  const bsRef = useRef(null);
  const isEdit = Boolean(entry);
  const item = isEdit && entry.kind === 'item' ? entry.row : null;
  const transfer = isEdit && entry.kind === 'transfer' ? entry.row : null;
  const [kind, setKind] = useState(isEdit && entry.kind === 'transfer' ? 'transfer' : 'item');
  const activePeople = useMemo(() => trip.people.filter((p) => p.active), [trip]);

  const [state, setState] = useState(() => initialItemState(item, trip));
  const [tstate, setTState] = useState(() => initialTransferState(transfer, trip));
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
  function setT(patch) { setTState((s) => ({ ...s, ...patch })); }

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

  function payerChanged(personId) {
    set({ payerId: personId, walletId: defaultWalletFor(trip, personId)?.id ?? null });
  }

  function buildItemBody() {
    const amount = parse(state.amount, locale);
    return {
      name: state.name.trim(),
      amount,
      currency_id: state.currencyId,
      payer_id: state.payerId,
      wallet_id: state.walletId,
      country_id: state.countryId,
      occurred_at: fromInputValue(state.occurredAt),
      labels: state.labels,
      city: state.city.trim() || null,
      map_url: state.mapUrl.trim() || null,
      lat: state.lat === '' ? null : state.lat,
      lon: state.lon === '' ? null : state.lon,
      split_mode: state.splitMode,
      shares: splitBody(),
    };
  }

  function buildTransferBody() {
    return {
      from_wallet_id: tstate.fromWalletId,
      from_amount: parse(tstate.fromAmount, locale),
      from_currency_id: tstate.fromCurrencyId,
      to_wallet_id: tstate.toWalletId,
      to_amount: parse(tstate.toAmount, locale),
      to_currency_id: tstate.toCurrencyId,
      occurred_at: fromInputValue(tstate.occurredAt),
      note: tstate.note.trim() || null,
    };
  }

  function fromAmountChanged(e) {
    const value = e.target.value;
    setTState((s) => ({ ...s, fromAmount: value, toAmount: s.toEdited ? s.toAmount : value }));
  }

  function fromCurrencyChanged(e) {
    const value = Number(e.target.value);
    setTState((s) => ({ ...s, fromCurrencyId: value, toCurrencyId: s.toEdited ? s.toCurrencyId : value }));
  }

  function toAmountChanged(e) {
    setT({ toAmount: e.target.value, toEdited: true });
  }

  function toCurrencyChanged(e) {
    setT({ toCurrencyId: Number(e.target.value), toEdited: true });
  }

  async function save(e, again) {
    e.preventDefault();
    const form = e.target.closest('form');
    if (form && !form.reportValidity()) return;
    setSaving(true);
    setFieldErrors({});
    try {
      if (kind === 'item') {
        const body = buildItemBody();
        const hadNewLabel = state.labels.some((name) => !labels.some((l) => l.name.toLowerCase() === name));
        if (isEdit) await api.patch(`/trips/${trip.slug}/items/${item.id}`, body);
        else await api.post(`/trips/${trip.slug}/items`, body);
        await reload('items');
        if (hadNewLabel) await reload('labels');
      } else {
        const body = buildTransferBody();
        if (isEdit) await api.patch(`/trips/${trip.slug}/transfers/${transfer.id}`, body);
        else await api.post(`/trips/${trip.slug}/transfers`, body);
        await reload('items');
      }
      invalidateMoneyViews();
      if (again && !isEdit && kind === 'item') {
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
    const confirmMsg = kind === 'item' ? t('item.delete_confirm') : t('transfer.delete_confirm');
    if (!window.confirm(confirmMsg)) return;
    try {
      if (kind === 'item') await api.del(`/trips/${trip.slug}/items/${item.id}`);
      else await api.del(`/trips/${trip.slug}/transfers/${transfer.id}`);
      await reload('items');
      invalidateMoneyViews();
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

  const title = isEdit
    ? (kind === 'item' ? t('item.edit_title') : t('transfer.edit_title'))
    : (kind === 'item' ? t('item.new_title') : t('transfer.new_title'));

  return html`
    <div class="modal fade" ref=${modalRef} tabindex="-1">
      <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-fullscreen-sm-down">
        <form class="modal-content" onSubmit=${(e) => save(e, false)}>
          <div class="modal-header py-2 ${isEdit && kind === 'item' ? 'bg-warning-subtle border-warning-subtle' : ''}">
            <h2 class="modal-title h6 mb-0 d-flex align-items-center gap-2">
              <i class="bi ${isEdit ? 'bi-pencil' : 'bi-plus-circle'}"></i>
              ${title}
            </h2>
            ${!isEdit && html`
              <div class="btn-group btn-group-sm ms-2" role="group">
                <button type="button" class="btn ${kind === 'item' ? 'btn-primary' : 'btn-outline-primary'}"
                        onClick=${() => setKind('item')}>${t('item.kind.expense')}</button>
                <button type="button" class="btn ${kind === 'transfer' ? 'btn-primary' : 'btn-outline-primary'}"
                        onClick=${() => setKind('transfer')}>${t('item.kind.transfer')}</button>
              </div>
            `}
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label=${t('action.close')}></button>
          </div>

          <div class="modal-body">
            ${kind === 'transfer' && html`
              <${TransferFields} trip=${trip} state=${tstate} fieldError=${fieldError}
                                  onFromWallet=${(e) => setT({ fromWalletId: Number(e.target.value) })}
                                  onFromAmount=${fromAmountChanged} onFromCurrency=${fromCurrencyChanged}
                                  onToWallet=${(e) => setT({ toWalletId: Number(e.target.value) })}
                                  onToAmount=${toAmountChanged} onToCurrency=${toCurrencyChanged}
                                  onNote=${(e) => setT({ note: e.target.value })}
                                  onOccurredAt=${(e) => setT({ occurredAt: e.target.value })} />
            `}

            ${kind === 'item' && html`
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
                                checked=${state.payerId === p.id} onChange=${() => payerChanged(p.id)} />
              `)}
            </div>

            <label class="form-label small mb-1">${t('item.wallet_label')}</label>
            <select class="form-select mb-3 ${fieldErrors.wallet_id ? 'is-invalid' : ''}" name="wallet_id"
                    value=${state.walletId ?? ''} onChange=${(e) => set({ walletId: Number(e.target.value) })}>
              ${walletsFor(trip, state.payerId).map((w) => html`<option key=${w.id} value=${w.id}>${w.name}</option>`)}
            </select>
            ${fieldError('wallet_id')}

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
              <div class="col-12 col-sm-6">
                <label class="form-label small mb-1">${t('item.city_label')}
                  <span class="text-body-secondary">${t('item.city_optional')}</span></label>
                <input class="form-control ${fieldErrors.city ? 'is-invalid' : ''}" name="city"
                       placeholder=${t('item.city_placeholder')}
                       value=${state.city} onInput=${(e) => set({ city: e.target.value })} />
                ${fieldError('city')}
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
            `}
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
            ${!isEdit && kind === 'item' && html`
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
