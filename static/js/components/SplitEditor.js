import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { money, fmtParams } from '../fmt.js';
import { Avatar } from './Avatar.js';

const MODES = ['equal', 'shares', 'exact'];

// Collapsed to one line while it's a plain equal split; expands to mode switch
// + one row per active person. Never computes a share itself (rule 2) — every
// number shown comes from the `preview` prop, which is the server's last
// preview-split (or saved item) response, rendered as given.
export function SplitEditor({
  people, mode, onModeChange, included, onToggle, weights, onWeightChange,
  exacts, onExactChange, preview, previewFailed, previewError, locale,
}) {
  const owedFor = (personId) => preview?.shares.find((s) => s.person_id === personId)?.owed;
  const activeCount = people.filter((p) => included.has(p.id)).length;

  const summary = mode === 'exact'
    ? t('split.exact')
    : mode === 'shares'
      ? t('split.weights', { weights: people.filter((p) => included.has(p.id)).map((p) => weights[p.id] ?? '1').join('·') })
      : activeCount === people.length
        ? t('split.equal', { n: activeCount })
        : t('split.equal_partial', { n: activeCount, total: people.length });

  const first = preview?.shares.find((s) => s.owed !== null)?.owed;

  return html`
    <div class="border rounded">
      <button class="btn btn-sm w-100 text-start d-flex align-items-center gap-2 py-2" type="button"
              data-bs-toggle="collapse" data-bs-target="#split-body">
        <i class="bi bi-people"></i>
        <span>${t('split.section')} <b>${summary}</b></span>
        ${mode === 'equal' && first !== undefined && html`
          <span class="num text-body-secondary ms-auto ${previewFailed ? 'opacity-50' : ''}">${t('split.each', { amount: money(first, locale) })}</span>
        `}
        <i class="bi bi-chevron-down"></i>
      </button>
      <div class="collapse" id="split-body">
        <div class="px-3 pb-3 border-top pt-3">
          <div class="btn-group btn-group-sm d-flex mb-2" role="group">
            ${MODES.map((m) => html`
              <button key=${m} type="button" class="btn ${mode === m ? 'btn-primary' : 'btn-outline-primary'}"
                      onClick=${() => onModeChange(m)}>${t(`split.mode.${m}`)}</button>
            `)}
          </div>
          <ul class="list-group list-group-flush ${previewFailed ? 'opacity-50' : ''}">
            ${people.map((p) => {
              const owed = owedFor(p.id);
              const isIn = included.has(p.id);
              return html`
                <li key=${p.id} class="list-group-item d-flex align-items-center px-0 py-2 gap-2">
                  <div class="form-check form-switch mb-0">
                    <input class="form-check-input" type="checkbox" id="split-${p.id}"
                           checked=${isIn} onChange=${() => onToggle(p.id)} />
                    <label class="form-check-label" for="split-${p.id}"><${Avatar} person=${p} /> ${p.name}</label>
                  </div>
                  ${mode === 'shares' && isIn && html`
                    <input class="form-control form-control-sm num text-end ms-auto" style="width:5rem" inputmode="decimal"
                           value=${weights[p.id] ?? '1'} onInput=${(e) => onWeightChange(p.id, e.target.value, false)}
                           onChange=${(e) => onWeightChange(p.id, e.target.value, true)} />
                  `}
                  ${mode === 'exact' && isIn && html`
                    <input class="form-control form-control-sm num text-end ms-auto" style="width:6rem" inputmode="decimal"
                           value=${exacts[p.id] ?? ''} onInput=${(e) => onExactChange(p.id, e.target.value, false)}
                           onChange=${(e) => onExactChange(p.id, e.target.value, true)} />
                  `}
                  ${mode !== 'shares' && mode !== 'exact' && html`
                    <span class="ms-auto num text-body-secondary">${isIn && owed !== null && owed !== undefined ? money(owed, locale) : '—'}</span>
                  `}
                </li>
              `;
            })}
          </ul>
          ${previewError && html`
            <div class="alert alert-danger py-2 px-3 small mt-2 mb-0">
              ${t('err.' + previewError.code, fmtParams(previewError.params, locale))}
            </div>
          `}
          ${!previewError && html`
            <div class="alert alert-primary py-2 px-3 small mt-2 mb-0">${t('split.hint')}</div>
          `}
        </div>
      </div>
    </div>
  `;
}
