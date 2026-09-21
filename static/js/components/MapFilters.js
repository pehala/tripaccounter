import { html } from '../h.js';
import { t } from '../i18n/index.js';

export const NO_FILTERS = { needle: '', labels: [], from: '', to: '' };

function toggled(names, name) {
  return names.includes(name) ? names.filter((other) => other !== name) : [...names, name];
}

export function MapFilters({ filters, labels, onChange }) {
  const active = Boolean(filters.needle || filters.labels.length > 0 || filters.from || filters.to);

  return html`
    <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <div class="input-group input-group-sm" style="max-width:16rem">
        <span class="input-group-text bg-body"><i class="bi bi-search"></i></span>
        <input class="form-control" placeholder=${t('items.filter_placeholder')}
               value=${filters.needle} onInput=${(e) => onChange({ needle: e.target.value })} />
      </div>
      <input type="date" class="form-control form-control-sm" style="max-width:9.5rem"
             aria-label=${t('map.from')} value=${filters.from}
             onInput=${(e) => onChange({ from: e.target.value })} />
      <input type="date" class="form-control form-control-sm" style="max-width:9.5rem"
             aria-label=${t('map.to')} value=${filters.to}
             onInput=${(e) => onChange({ to: e.target.value })} />
      ${active && html`
        <button type="button" class="btn btn-sm btn-link px-1"
                onClick=${() => onChange(NO_FILTERS)}>${t('map.clear')}</button>`}
    </div>
    ${labels.length > 0 && html`
      <div class="d-flex flex-wrap gap-1 mb-3" role="group" aria-label=${t('map.labels')}>
        ${labels.map((name) => html`
          <button key=${name} type="button" aria-pressed=${filters.labels.includes(name)}
                  class="btn btn-sm rounded-pill ${filters.labels.includes(name) ? 'btn-primary' : 'btn-outline-secondary'}"
                  onClick=${() => onChange({ labels: toggled(filters.labels, name) })}>${name}</button>
        `)}
      </div>`}
  `;
}
