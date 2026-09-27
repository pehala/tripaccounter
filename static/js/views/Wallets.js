import { useEffect } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { money, rate } from '../fmt.js';
import { Avatar } from '../components/Avatar.js';
import { Loading } from '../components/Loading.js';

function RatesFooter({ rows, locale }) {
  if (rows.length === 0) return null;
  return html`
    <div class="card-footer small">
      <div class="text-body-secondary">${t('wallets.rates')}</div>
      ${rows.map((row) => html`
        <div key=${`${row.from_currency_code}-${row.to_currency_code}`} class="exchange-rate num">
          ${row.rate === null
            ? t('wallets.no_rate', { from: row.from_currency_code, to: row.to_currency_code })
            : `1 ${row.to_currency_code} = ${rate(row.rate, locale)} ${row.from_currency_code}`}
          ${row.leftover_rate !== null && html`
            <span class="exchange-leftover text-body-secondary"> · ${t('wallets.leftover', {
              amount: `${money(row.leftover, locale)} ${row.to_currency_code}`,
              rate: `1 ${row.to_currency_code} = ${rate(row.leftover_rate, locale)} ${row.from_currency_code}`,
            })}</span>
          `}
        </div>
      `)}
    </div>
  `;
}

function WalletRow({ wallet, locale }) {
  return html`
    <li class="list-group-item">
      <div class="d-flex justify-content-between align-items-center">
        <span>${wallet.name}</span>
        ${!wallet.tracked && html`<small class="text-body-secondary">${t('wallets.untracked')}</small>`}
      </div>
      ${wallet.tracked && wallet.balances.length === 0 && html`
        <small class="text-body-secondary">${t('wallets.no_activity')}</small>
      `}
      ${wallet.tracked && wallet.balances.map((b) => {
        const overcharged = b.balance < 0;
        return html`
          <div key=${b.currency_id} class="d-flex align-items-center gap-2 mt-1">
            <small class="text-body-secondary flex-grow-1 num">
              ${t('wallets.flow', {
                received: `${money(b.received, locale)} ${b.currency_code}`,
                sent: `${money(b.sent, locale)} ${b.currency_code}`,
                spent: `${money(b.spent, locale)} ${b.currency_code}`,
              })}
            </small>
            <span class="num fw-semibold text-end ${overcharged ? 'text-danger' : ''}">
              ${overcharged && html`<i class="bi bi-exclamation-triangle-fill me-1"></i>`}
              ${money(b.balance, locale)} ${b.currency_code}
            </span>
          </div>
          ${overcharged && html`<div class="small text-danger">${t('wallets.overcharge')}</div>`}
        `;
      })}
    </li>
  `;
}

export function Wallets() {
  const store = useStore();
  const locale = getLocale();

  useEffect(() => {
    if (!store.wallets) reload('wallets');
    if (!store.exchangeRates) reload('exchangeRates');
  }, [store.slug]);

  if (!store.wallets || !store.exchangeRates) return html`<${Loading} />`;

  const byPerson = new Map();
  for (const wallet of store.wallets) {
    if (!byPerson.has(wallet.person_id)) byPerson.set(wallet.person_id, []);
    byPerson.get(wallet.person_id).push(wallet);
  }

  if (store.wallets.length === 0) return html`<p class="text-body-secondary">${t('wallets.empty')}</p>`;

  return html`
    ${store.trip.people.map((person) => {
      const wallets = byPerson.get(person.id) || [];
      if (wallets.length === 0) return null;
      return html`
        <div key=${person.id} class="card shadow-sm mb-3">
          <div class="card-header fw-semibold"><${Avatar} person=${person} /> ${person.name}</div>
          <ul class="list-group list-group-flush">
            ${wallets.map((w) => html`<${WalletRow} key=${w.id} wallet=${w} locale=${locale} />`)}
          </ul>
          <${RatesFooter} rows=${store.exchangeRates.filter((row) => row.person_id === person.id)} locale=${locale} />
        </div>
      `;
    })}
  `;
}
