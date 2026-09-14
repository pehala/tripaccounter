import { html } from '../h.js';
import { t } from '../i18n/index.js';

// Wallet selects group by owner so a cross-owner pick is one click; the to
// side is visually secondary (design/WALLETS.md §4) until the user edits it
// away from the from side's mirrored amount/currency.
export function TransferFields({
  trip, state, fieldError,
  onFromWallet, onFromAmount, onFromCurrency,
  onToWallet, onToAmount, onToCurrency,
  onNote, onOccurredAt,
}) {
  const owners = trip.people.filter((p) => (trip.wallets || []).some((w) => w.person_id === p.id));

  function walletOptions() {
    return owners.map((p) => html`
      <optgroup key=${p.id} label=${p.name}>
        ${(trip.wallets || []).filter((w) => w.person_id === p.id).map((w) => html`
          <option key=${w.id} value=${w.id}>${w.name}</option>
        `)}
      </optgroup>
    `);
  }

  return html`
    <div class="mb-3">
      <label class="form-label small mb-1">${t('transfer.from_label')}</label>
      <select class="form-select mb-2 ${fieldError('from_wallet_id') ? 'is-invalid' : ''}" required
              value=${state.fromWalletId ?? ''} onChange=${onFromWallet}>
        <option value="" disabled>—</option>
        ${walletOptions()}
      </select>
      <div class="input-group">
        <input class="form-control num ${fieldError('from_amount') ? 'is-invalid' : ''}" inputmode="decimal"
               placeholder="0" required value=${state.fromAmount} onInput=${onFromAmount} />
        <select class="form-select flex-grow-0 w-auto" value=${state.fromCurrencyId} onChange=${onFromCurrency}>
          ${trip.currencies.map((c) => html`<option key=${c.id} value=${c.id}>${c.code}</option>`)}
        </select>
      </div>
      ${fieldError('from_wallet_id')}${fieldError('from_amount')}
    </div>

    <div class="mb-3 ${state.toEdited ? '' : 'opacity-75'}">
      <label class="form-label small mb-1">${t('transfer.to_label')}</label>
      <select class="form-select mb-2 ${fieldError('to_wallet_id') ? 'is-invalid' : ''}" required
              value=${state.toWalletId ?? ''} onChange=${onToWallet}>
        <option value="" disabled>—</option>
        ${walletOptions()}
      </select>
      <label class="form-label small mb-1">${t('transfer.receives_label')}</label>
      <div class="input-group">
        <input class="form-control num" inputmode="decimal" placeholder="0" required
               value=${state.toAmount} onInput=${onToAmount} />
        <select class="form-select flex-grow-0 w-auto ${fieldError('to_currency_id') ? 'is-invalid' : ''}"
                value=${state.toCurrencyId} onChange=${onToCurrency}>
          ${trip.currencies.map((c) => html`<option key=${c.id} value=${c.id}>${c.code}</option>`)}
        </select>
      </div>
      ${fieldError('to_wallet_id')}${fieldError('to_currency_id')}
    </div>

    <div class="row g-3">
      <div class="col-12 col-sm-6">
        <label class="form-label small mb-1">${t('item.when_label')}</label>
        <input type="datetime-local" class="form-control ${fieldError('occurred_at') ? 'is-invalid' : ''}"
               value=${state.occurredAt} onChange=${onOccurredAt} />
        ${fieldError('occurred_at')}
      </div>
      <div class="col-12 col-sm-6">
        <label class="form-label small mb-1">${t('transfer.note_placeholder')}</label>
        <input class="form-control" placeholder=${t('transfer.note_placeholder')}
               value=${state.note} onInput=${onNote} />
      </div>
    </div>
  `;
}
