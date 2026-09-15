import { html } from '../h.js';
import { errText } from './errText.js';

export function FieldError({ error, locale }) {
  if (!error) return null;
  return html`<div class="invalid-feedback d-block">${errText(error, locale)}</div>`;
}
