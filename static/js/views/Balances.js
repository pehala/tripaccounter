import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { money, signed } from '../fmt.js';
import { getRatesState, setTargetCurrency, setRateValue } from '../rates.js';
import { rateFor, convert, combineGroup, combineSuggestions } from '../convert.js';
import { Loading } from '../components/Loading.js';
import { CollapsibleSection } from '../components/CollapsibleSection.js';
import { RatesForm } from '../components/RatesForm.js';
import { SideNav, MobilePillNav } from '../components/SideNav.js';

// Shared renderer for a currency's own balance *or* the Total's converted
// figures. `showNote` is false for the Total: its settle-up list isn't the
// real, never-converted one the note describes.
function BalanceBlock({ id, badgeLabel, code, totalSpent, people, suggestions, trip, locale, extra, showSections = true, showNote = true }) {
  const personName = (pid) => trip.people.find((p) => p.id === pid)?.name || '';
  const maxAbs = Math.max(1e-9, ...[...people.values()].map((net) => Math.abs(net)));

  return html`
    <section id="cur-${id}" class="mb-4">
      <h2 class="h6 d-flex align-items-center gap-2 pt-2">
        <span class="badge text-bg-primary">${badgeLabel}</span>
        ${totalSpent !== null && html`<b class="num">${t('balances.spent', { amount: `${money(totalSpent, locale)} ${code}` })}</b>`}
      </h2>

      ${extra}

      ${showSections && html`
        <${CollapsibleSection} id="sec-${id}-net" icon="bi-bar-chart" title=${t('balances.title')}>
          <ul class="list-group list-group-flush">
            ${trip.people.filter((p) => people.has(p.id)).map((p) => {
              const net = people.get(p.id);
              const width = (Math.abs(net) / maxAbs) * 50;
              const cls = net > 0 ? 'text-success' : net < 0 ? 'text-danger' : 'text-body-secondary';
              return html`
                <li key=${p.id} class="list-group-item d-flex align-items-center gap-3">
                  <span style="width:4.5rem">${p.name}</span>
                  <span class="bal-bar flex-grow-1 position-relative rounded-pill bg-body-tertiary">
                    ${net !== 0 && html`<i class="position-absolute top-0 bottom-0 rounded-pill ${net > 0 ? 'start-50 bg-success' : 'end-50 bg-danger'}" style="width:${width}%"></i>`}
                  </span>
                  <span class="num ${cls} fw-semibold text-end" style="width:6rem">${signed(net, locale)}</span>
                </li>
              `;
            })}
          </ul>
        <//>

        <${CollapsibleSection} id="sec-${id}-settle_up" icon="bi-arrow-left-right" defaultOpen=${true}
                                title=${t('balances.settle_up')} summary=${t('balances.transfers', { n: suggestions.length })}>
          <ul class="list-group list-group-flush">
            ${suggestions.map((s, i) => html`
              <li key=${i} class="list-group-item d-flex align-items-center gap-2">
                ${personName(s.from_person_id)} <i class="bi bi-arrow-right"></i> ${personName(s.to_person_id)}
                <b class="num ms-auto">${money(s.amount, locale)} ${code}</b>
              </li>
            `)}
          </ul>
          ${showNote && html`<div class="alert alert-primary py-2 px-3 small mt-2 mb-0">${t('balances.note')}</div>`}
        <//>
      `}
    </section>
  `;
}

function CurrencyBalanceBlock({ balance, trip, locale }) {
  const people = new Map(balance.people.map((p) => [p.person_id, p.net]));

  return html`
    <${BalanceBlock} id=${balance.currency_id} badgeLabel=${balance.currency_code} code=${balance.currency_code}
                      totalSpent=${balance.total_spent} people=${people} suggestions=${balance.suggestions}
                      trip=${trip} locale=${locale} />
  `;
}

// Converted, pair-netted totals — never a fresh minimum-transfer plan (that
// stays `settle.py`'s job; this only converts and sums per-currency results).
function TotalBalances({ balances, trip, ratesState, onTargetChange, onRateChange, locale }) {
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const target = trip.currencies.find((c) => c.id === ratesState.target) || primary;
  const values = ratesState.values;

  const allRatesSet = trip.currencies.every((c) => rateFor(c.id, target.id, values, locale) !== null);

  const totalSpent = allRatesSet
    ? balances.reduce((sum, b) => sum + convert(b.total_spent, rateFor(b.currency_id, target.id, values, locale)), 0)
    : null;
  const people = allRatesSet ? combineGroup(balances, 'people', 'person_id', target.id, values, locale, 'net') : new Map();
  const suggestions = allRatesSet ? combineSuggestions(balances, target.id, values, locale) : [];

  const extra = html`
    <${RatesForm} trip=${trip} target=${target} values=${values} onTargetChange=${onTargetChange} onRateChange=${onRateChange} />
    ${!allRatesSet && html`<div class="alert alert-secondary py-2 px-3 small mb-0">${t('rates.missing')}</div>`}
    ${allRatesSet && html`<div class="small text-body-secondary mb-2">${t('rates.total_note')}</div>`}
  `;

  return html`
    <${BalanceBlock} id="total" badgeLabel=${t('nav.total')} code=${target.code} totalSpent=${totalSpent}
                      people=${people} suggestions=${suggestions} trip=${trip} locale=${locale}
                      extra=${extra} showSections=${allRatesSet} showNote=${false} />
  `;
}

export function Balances() {
  const store = useStore();
  const locale = getLocale();
  const [ratesState, setRatesState] = useState(() => getRatesState(store.slug));

  useEffect(() => {
    if (!store.balances) reload('balances');
  }, [store.slug]);

  if (!store.balances) return html`<${Loading} />`;

  const trip = store.trip;
  const multiCurrency = trip.currencies.length > 1;

  function onTargetChange(currencyId) {
    setRatesState(setTargetCurrency(store.slug, currencyId));
  }

  function onRateChange(currencyId, value) {
    setRatesState(setRateValue(store.slug, currencyId, value));
  }

  const groups = [
    { key: 'net', title: t('balances.title') },
    { key: 'settle_up', title: t('balances.settle_up') },
  ];
  const entries = [
    ...(multiCurrency ? [{ id: 'total', label: t('nav.total'), groups }] : []),
    ...store.balances.map((balance) => ({ id: balance.currency_id, label: balance.currency_code, groups })),
  ];

  return html`
    <${MobilePillNav} entries=${entries} />
    <div class="row g-3">
      <div class="d-none d-md-block col-md-4 col-lg-3">
        <${SideNav} entries=${entries} ariaLabel=${t('nav.jump_to')} />
      </div>
      <div class="col-md-8 col-lg-9 balances-content">
        ${multiCurrency && html`<${TotalBalances} balances=${store.balances} trip=${trip} ratesState=${ratesState} onTargetChange=${onTargetChange} onRateChange=${onRateChange} locale=${locale} />`}
        ${store.balances.map((balance) => html`<${CurrencyBalanceBlock} key=${balance.currency_id} balance=${balance} trip=${trip} locale=${locale} />`)}
      </div>
    </div>
  `;
}
