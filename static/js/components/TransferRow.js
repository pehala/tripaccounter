import { html } from '../h.js';
import { money } from '../fmt.js';
import { Avatar } from './Avatar.js';

// Same shell as ItemRow, so the two kinds of feed row line up - the amount is
// muted rather than bold, so it never reads as spending (design/WALLETS.md §1.8).
// One line: a transfer has no name to give it a title line of its own, so time
// and note share the line with the wallet flow instead of a line to themselves.
export function TransferRow({ transfer, trip, locale, onSelect }) {
  const wallet = (id) => (trip.wallets || []).find((w) => w.id === id);
  const owner = (id) => trip.people.find((p) => p.id === wallet(id)?.person_id);
  const fromWallet = wallet(transfer.from_wallet_id);
  const toWallet = wallet(transfer.to_wallet_id);
  const fromOwner = owner(transfer.from_wallet_id);
  const toOwner = owner(transfer.to_wallet_id);
  const time = transfer.occurred_at.slice(11, 16);
  const isExchange = transfer.from_currency_code !== transfer.to_currency_code;

  return html`
    <a href="#" class="list-group-item list-group-item-action d-flex align-items-center gap-3 transfer-row"
       onClick=${(e) => { e.preventDefault(); onSelect?.(transfer); }}>
      <i class="bi bi-arrow-left-right text-body-secondary"></i>
      <span class="flex-grow-1 min-w-0 d-flex align-items-center flex-wrap gap-2 item-line">
        <span class="d-inline-flex align-items-center gap-1"><${Avatar} person=${fromOwner} />${fromWallet?.name}</span>
        <i class="bi bi-arrow-right text-body-secondary"></i>
        <span class="d-inline-flex align-items-center gap-1"><${Avatar} person=${toOwner} />${toWallet?.name}</span>
        <small class="text-body-secondary">${time}${transfer.note ? ` · ${transfer.note}` : ''}</small>
      </span>
      <span class="text-end num text-nowrap text-body-secondary">
        ${money(transfer.from_amount, locale)} ${transfer.from_currency_code}
        ${isExchange && html` <i class="bi bi-arrow-right"></i> ${money(transfer.to_amount, locale)} ${transfer.to_currency_code}`}
      </span>
    </a>
  `;
}
