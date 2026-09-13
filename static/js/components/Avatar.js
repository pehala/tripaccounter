import { html } from '../h.js';

export function Avatar({ person, size }) {
  if (!person) return null;
  const cls = size === 'lg' ? 'av av-lg' : 'av';
  return html`<i class=${cls} style="background:${person.color}">${person.initial}</i>`;
}
