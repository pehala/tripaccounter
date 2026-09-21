import { html } from '../h.js';
import { Avatar } from './Avatar.js';

// input + label pair for a Bootstrap btn-check toggle group — a parent renders
// several of these inside one `<div class="d-flex flex-wrap gap-1">`.
export function PersonChip({ person, type = 'radio', id, name, checked, onChange, after }) {
  return html`
    <input type=${type} class="btn-check" id=${id} name=${name} checked=${checked} onChange=${onChange} autocomplete="off" />
    <label class="btn btn-sm btn-outline-primary rounded-pill d-inline-flex align-items-center gap-1" for=${id}><${Avatar} person=${person} /> ${person.name}${after != null ? html` <span class="ms-1">${after}</span>` : ''}</label>
  `;
}
