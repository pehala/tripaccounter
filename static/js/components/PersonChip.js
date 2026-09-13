import { html } from '../h.js';
import { Avatar } from './Avatar.js';

// input + label pair for the `.who` toggle group (app.css) — a parent renders
// several of these inside one `<div class="who d-flex flex-wrap gap-1">`.
export function PersonChip({ person, type = 'radio', id, name, checked, onChange, after }) {
  return html`
    <input type=${type} id=${id} name=${name} checked=${checked} onChange=${onChange} />
    <label for=${id}><${Avatar} person=${person} /> ${person.name}${after != null ? html` <span class="ms-1">${after}</span>` : ''}</label>
  `;
}
