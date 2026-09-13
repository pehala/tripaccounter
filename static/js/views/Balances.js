import { useEffect } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { BalanceCard } from '../components/BalanceCard.js';

export function Balances() {
  const store = useStore();
  const locale = getLocale();

  useEffect(() => {
    if (!store.balances) reload('balances');
  }, [store.slug]);

  if (!store.balances) return html`<p>${t('app.loading')}</p>`;

  return html`
    ${store.balances.map((balance) => html`
      <${BalanceCard} key=${balance.currency_id} balance=${balance} trip=${store.trip} locale=${locale} />
    `)}
  `;
}
