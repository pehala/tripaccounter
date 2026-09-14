import { html } from '../h.js';
import { date as fmtDate, money } from '../fmt.js';
import { ItemRow } from './ItemRow.js';
import { TransferRow } from './TransferRow.js';

// Date header + its rows. The day total is `items.day_totals`, one row per
// currency, summed server-side (design/FRONTEND.md §4 rule 1) — never accumulated
// here from the day's own rows, and expenses only: a transfer is movement, not
// spending. Rounded up to a whole unit for this display only; the exact figure
// still lives in each item row.
export function DayGroup({ date, entries, totals, trip, locale, onSelect }) {
  const weekday = new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(new Date(date));
  const label = `${weekday} ${fmtDate(date, locale)}`;
  return html`
    <div class="day-sep d-flex align-items-center gap-2 bg-body-tertiary py-1">
      <small class="text-body-secondary text-uppercase fw-semibold">${label}</small>
      <hr class="flex-grow-1 my-0 opacity-25" />
      <small class="num text-body-secondary text-nowrap">
        ${(totals || []).map((t) => html`<span key=${t.currency_id} class="ms-2">${money(Math.ceil(t.amount), locale)} ${t.currency_code}</span>`)}
      </small>
    </div>
    <div class="list-group item-list shadow-sm mb-3">
      ${entries.map((entry) => entry.kind === 'transfer'
        ? html`<${TransferRow} key="transfer-${entry.row.id}" transfer=${entry.row} trip=${trip} locale=${locale}
                               onSelect=${() => onSelect(entry)} />`
        : html`<${ItemRow} key="item-${entry.row.id}" item=${entry.row} trip=${trip} locale=${locale}
                           onSelect=${() => onSelect(entry)} />`)}
    </div>
  `;
}
