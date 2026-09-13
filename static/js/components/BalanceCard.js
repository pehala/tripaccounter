import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { money, signed } from '../fmt.js';

export function BalanceCard({ balance, trip, locale }) {
  const personName = (id) => trip.people.find((p) => p.id === id)?.name || '';
  const maxAbs = Math.max(1e-9, ...balance.people.map((p) => Math.abs(p.net)));

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t('balances.title')} <span class="badge text-bg-primary">${balance.currency_code}</span></span>
        <small class="text-body-secondary num">${t('balances.spent', { amount: `${money(balance.total_spent, locale)} ${balance.currency_code}` })}</small>
      </div>
      <ul class="list-group list-group-flush">
        ${balance.people.map((p) => {
          const width = (Math.abs(p.net) / maxAbs) * 50;
          const cls = p.net > 0 ? 'text-success' : p.net < 0 ? 'text-danger' : 'text-body-secondary';
          return html`
            <li key=${p.person_id} class="list-group-item d-flex align-items-center gap-3">
              <span style="width:4.5rem">${personName(p.person_id)}</span>
              <span class="bal-bar flex-grow-1">
                ${p.net !== 0 && html`<i class=${p.net > 0 ? 'p' : 'n'} style="width:${width}%"></i>`}
              </span>
              <span class="num ${cls} fw-semibold text-end" style="width:6rem">${signed(p.net, locale)}</span>
            </li>
          `;
        })}
      </ul>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('balances.settle_up')} <span class="badge text-bg-primary">${balance.currency_code}</span>
        <small class="text-body-secondary fw-normal">— ${t('balances.transfers', { n: balance.suggestions.length })}</small></div>
      <ul class="list-group list-group-flush">
        ${balance.suggestions.map((s, i) => html`
          <li key=${i} class="list-group-item d-flex align-items-center gap-2">
            ${personName(s.from_person_id)} <i class="bi bi-arrow-right"></i> ${personName(s.to_person_id)}
            <b class="num ms-auto">${money(s.amount, locale)} ${balance.currency_code}</b>
          </li>
        `)}
      </ul>
      <div class="card-body pt-2">
        <div class="alert alert-primary py-2 px-3 small mb-0">${t('balances.note')}</div>
      </div>
    </div>
  `;
}
