import { useEffect } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { getLocale } from '../i18n/index.js';
import { BalanceCard } from '../components/BalanceCard.js';
import { Loading } from '../components/Loading.js';

export function Balances() {
  const store = useStore();
  const locale = getLocale();

  useEffect(() => {
    if (!store.balances) reload('balances');
  }, [store.slug]);

  if (!store.balances) return html`<${Loading} />`;

  return html`
    ${store.balances.map((balance) => html`
      <${BalanceCard} key=${balance.currency_id} balance=${balance} trip=${store.trip} locale=${locale} />
    `)}
  `;
}
