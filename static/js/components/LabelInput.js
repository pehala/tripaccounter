import { useState } from 'preact/hooks';
import { html } from '../h.js';
import { t } from '../i18n/index.js';

// A label is one token with no whitespace inside it — anything typed with a
// space or comma is folded into one with dashes, same as the mockup's JS.
const normalize = (raw) => raw.trim().toLowerCase().replace(/[\s,]+/g, '-').replace(/^-+|-+$/g, '');

// Space- or comma-separated chips. Enter is left alone so it submits the form
// like any other input (design/FRONTEND.md §2).
export function LabelInput({ value, onChange, suggestions = [], listId = 'label-suggestions' }) {
  const [typed, setTyped] = useState('');

  function commit(raw) {
    const tokens = raw.split(/[\s,]+/).map(normalize).filter(Boolean);
    if (!tokens.length) return;
    const next = [...value];
    for (const tok of tokens) if (!next.includes(tok)) next.push(tok);
    onChange(next);
    setTyped('');
  }

  function onKeyDown(e) {
    if (e.key === ' ' || e.key === ',') {
      e.preventDefault();
      if (typed.trim()) commit(typed);
    } else if (e.key === 'Backspace' && !typed) {
      e.preventDefault();
      onChange(value.slice(0, -1));
    }
  }

  return html`
    <div class="tag-input form-control d-flex flex-wrap align-items-center gap-1 p-1">
      ${value.map((name) => html`
        <span key=${name} class="badge rounded-pill text-bg-secondary d-inline-flex align-items-center gap-1">
          ${name}
          <button type="button" class="btn-close btn-close-white" style="font-size:.5rem"
                  aria-label=${t('action.remove')} onClick=${() => onChange(value.filter((v) => v !== name))}></button>
        </span>
      `)}
      <input class="border-0 flex-grow-1 bg-transparent" list=${listId} autocomplete="off"
             style="min-width:6rem;outline:0" value=${typed} placeholder=${t('item.labels_placeholder')}
             onInput=${(e) => setTyped(e.target.value)}
             onKeyDown=${onKeyDown}
             onChange=${(e) => { if (e.target.value.trim()) commit(e.target.value); }}
             onBlur=${(e) => { if (e.target.value.trim()) commit(e.target.value); }} />
    </div>
    <datalist id=${listId}>
      ${suggestions.filter((name) => !value.includes(name)).map((name) => html`<option key=${name} value=${name} />`)}
    </datalist>
  `;
}
