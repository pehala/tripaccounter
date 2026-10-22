import { useRef } from 'preact/hooks';
import { html } from '../h.js';

// Every IANA zone the browser knows, plus the one the field starts with: a trip may
// carry a zone this browser's list lacks, such as the `UTC` every existing trip has.
function zoneNames(initial) {
  const names = new Set(Intl.supportedValuesOf('timeZone'));
  if (initial) names.add(initial);
  return [...names].sort();
}

// A text field over a <datalist>: typing "tok" narrows the ~420 names to Asia/Tokyo,
// where a <select> would make the user scroll for it. A name outside the list is
// flagged here and refused by the server (`invalid_timezone`).
export function TimezoneSelect({ value, onChange, id, small, disabled = false }) {
  const initial = useRef(value).current;
  const names = zoneNames(initial);
  return html`
    <input id=${id} list="${id}-zones" autocomplete="off" spellcheck="false" disabled=${disabled}
           class="form-control ${small ? 'form-control-sm' : ''} ${names.includes(value) ? '' : 'is-invalid'}"
           value=${value} onInput=${(e) => onChange(e.target.value)} />
    <datalist id="${id}-zones">
      ${names.map((name) => html`<option key=${name} value=${name}></option>`)}
    </datalist>
  `;
}
