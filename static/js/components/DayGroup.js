import { html } from '../h.js';
import { date as fmtDate } from '../fmt.js';
import { ItemRow } from './ItemRow.js';

// Date header + its rows. No subtotal: that number is not in the API and the
// frontend may not compute one (design/FRONTEND.md §4 rule 1).
export function DayGroup({ date, items, trip, locale, onSelect }) {
  const weekday = new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(new Date(date));
  const label = `${weekday} ${fmtDate(date, locale)}`;
  return html`
    <div class="day-sep d-flex align-items-center gap-2 bg-body-tertiary py-1">
      <small class="text-body-secondary text-uppercase fw-semibold">${label}</small>
      <hr class="flex-grow-1 my-0 opacity-25" />
    </div>
    <div class="list-group item-list shadow-sm mb-3">
      ${items.map((item) => html`<${ItemRow} key=${item.id} item=${item} trip=${trip} locale=${locale} onSelect=${onSelect} />`)}
    </div>
  `;
}
