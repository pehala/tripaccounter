import { useEffect, useRef, useState } from 'preact/hooks';
import { html } from '../h.js';
import { api } from '../api.js';
import { t, getLocale } from '../i18n/index.js';
import { fmtParams } from '../fmt.js';
import { pushFlash } from './Flash.js';

function initialState(stay) {
  return {
    name: stay?.name ?? '',
    checkIn: stay?.check_in ?? '',
    checkOut: stay?.check_out ?? '',
    url: stay?.url ?? '',
    countryId: stay?.country_id ?? null,
    city: stay?.city ?? '',
    note: stay?.note ?? '',
    mapUrl: stay?.map_url ?? '',
    lat: stay?.lat ?? '',
    lon: stay?.lon ?? '',
  };
}

// Every field goes out on every save: a PATCH clears an optional field sent as
// `null`, so emptying an input is how a link or a country is removed.
function body(state) {
  return {
    name: state.name.trim(),
    check_in: state.checkIn,
    check_out: state.checkOut,
    url: state.url.trim() || null,
    country_id: state.countryId,
    city: state.city.trim() || null,
    note: state.note.trim() || null,
    map_url: state.mapUrl.trim() || null,
    lat: state.lat === '' ? null : state.lat,
    lon: state.lon === '' ? null : state.lon,
  };
}

export function StayModal({ trip, stay, onSaved, onClose }) {
  const locale = getLocale();
  const modalRef = useRef(null);
  const bsRef = useRef(null);
  const [state, setState] = useState(() => initialState(stay));
  const [fieldErrors, setFieldErrors] = useState({});
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

  async function save(e) {
    e.preventDefault();
    if (!e.target.reportValidity()) return;
    setSaving(true);
    setFieldErrors({});
    try {
      if (stay) await api.patch(`/trips/${trip.slug}/stays/${stay.id}`, body(state));
      else await api.post(`/trips/${trip.slug}/stays`, body(state));
      await onSaved();
      bsRef.current.hide();
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) setFieldErrors(err.fields);
      else pushFlash(t('err.' + err.code, fmtParams(err.params, locale)));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(t('stay.delete_confirm'))) return;
    try {
      await api.del(`/trips/${trip.slug}/stays/${stay.id}`);
      await onSaved();
      bsRef.current.hide();
    } catch (err) {
      pushFlash(t('err.' + err.code, fmtParams(err.params, locale)));
    }
  }

  function fieldError(name) {
    const err = fieldErrors[name];
    if (!err) return null;
    return html`<div class="invalid-feedback d-block">${t('err.' + err.code, fmtParams(err.params, locale))}</div>`;
  }

  const invalid = (name) => (fieldErrors[name] ? 'is-invalid' : '');

  return html`
    <div class="modal fade" ref=${modalRef} tabindex="-1">
      <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-fullscreen-sm-down">
        <form class="modal-content" onSubmit=${save}>
          <div class="modal-header py-2">
            <h2 class="modal-title h6 mb-0 d-flex align-items-center gap-2">
              <i class="bi ${stay ? 'bi-pencil' : 'bi-plus-circle'}"></i>
              ${stay ? t('stay.edit_title') : t('stay.new_title')}
            </h2>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label=${t('action.close')}></button>
          </div>

          <div class="modal-body">
            <div class="mb-3">
              <input class="form-control form-control-lg ${invalid('name')}" name="name"
                     placeholder=${t('stay.name_placeholder')} autocomplete="off" required autofocus
                     value=${state.name} onInput=${(e) => set({ name: e.target.value })} />
              ${fieldError('name')}
            </div>

            <div class="row g-3 mb-3">
              <div class="col-6">
                <label class="form-label small mb-1" for="stay-check-in">${t('stay.check_in')}</label>
                <input type="date" id="stay-check-in" name="check_in" required
                       class="form-control ${invalid('check_in')}"
                       value=${state.checkIn} onChange=${(e) => set({ checkIn: e.target.value })} />
                ${fieldError('check_in')}
              </div>
              <div class="col-6">
                <label class="form-label small mb-1" for="stay-check-out">${t('stay.check_out')}</label>
                <input type="date" id="stay-check-out" name="check_out" required min=${state.checkIn}
                       class="form-control ${invalid('check_out')}"
                       value=${state.checkOut} onChange=${(e) => set({ checkOut: e.target.value })} />
                ${fieldError('check_out')}
              </div>
            </div>

            <label class="form-label small mb-1" for="stay-url">${t('stay.url_label')}
              <span class="text-body-secondary">${t('item.city_optional')}</span></label>
            <input type="url" id="stay-url" name="url" class="form-control mb-3 ${invalid('url')}"
                   placeholder="https://…"
                   value=${state.url} onInput=${(e) => set({ url: e.target.value })} />
            ${fieldError('url')}

            <div class="row g-3 mb-3">
              <div class="col-12 col-sm-6">
                <label class="form-label small mb-1" for="stay-country">${t('item.country_label')}</label>
                <select id="stay-country" name="country_id" class="form-select ${invalid('country_id')}"
                        value=${state.countryId ?? ''}
                        onChange=${(e) => set({ countryId: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">${t('stay.none')}</option>
                  ${trip.countries.map((c) => html`<option key=${c.id} value=${c.id}>${c.flag} ${c.name}</option>`)}
                </select>
                ${fieldError('country_id')}
              </div>
              <div class="col-12 col-sm-6">
                <label class="form-label small mb-1" for="stay-city">${t('item.city_label')}</label>
                <input id="stay-city" name="city" class="form-control ${invalid('city')}"
                       placeholder=${t('item.city_placeholder')}
                       value=${state.city} onInput=${(e) => set({ city: e.target.value })} />
                ${fieldError('city')}
              </div>
            </div>

            <label class="form-label small mb-1">${t('item.location_label')}
              <span class="text-body-secondary">${t('item.location_optional')}</span></label>
            <div class="input-group mb-2">
              <span class="input-group-text"><i class="bi bi-geo-alt"></i></span>
              <input class="form-control ${invalid('map_url')}" name="map_url"
                     placeholder=${t('item.location_map_placeholder')}
                     value=${state.mapUrl} onInput=${(e) => set({ mapUrl: e.target.value })} />
            </div>
            ${fieldError('map_url')}
            <div class="input-group mb-3">
              <input class="form-control num ${invalid('lat')}" inputmode="decimal"
                     placeholder=${t('item.location_lat_placeholder')}
                     value=${state.lat} onInput=${(e) => set({ lat: e.target.value })} />
              <input class="form-control num ${invalid('lon')}" inputmode="decimal"
                     placeholder=${t('item.location_lon_placeholder')}
                     value=${state.lon} onInput=${(e) => set({ lon: e.target.value })} />
            </div>
            ${fieldError('lat')}${fieldError('lon')}

            <label class="form-label small mb-1" for="stay-note">${t('stay.note_label')}</label>
            <textarea id="stay-note" name="note" class="form-control ${invalid('note')}" rows="2"
                      value=${state.note} onInput=${(e) => set({ note: e.target.value })}></textarea>
            ${fieldError('note')}
          </div>

          <div class="modal-footer py-2">
            ${stay && html`
              <button type="button" class="btn btn-link link-danger text-decoration-none me-auto" onClick=${remove}>
                <i class="bi bi-trash"></i> ${t('item.delete')}</button>
            `}
            ${!stay && html`
              <button type="button" class="btn btn-link link-secondary text-decoration-none me-auto d-none d-sm-inline"
                      data-bs-dismiss="modal">${t('item.cancel')}</button>
            `}
            <button type="submit" class="btn btn-primary px-4" disabled=${saving}>${t('item.save')}</button>
          </div>
        </form>
      </div>
    </div>
  `;
}
