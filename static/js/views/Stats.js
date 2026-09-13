import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { money, parse, date as fmtDate } from '../fmt.js';
import { getRates, setRate } from '../rates.js';
import { LabelBadge } from '../components/LabelBadge.js';
import { Loading } from '../components/Loading.js';

function pct(amount, total) {
  return total > 0 ? Math.round((amount / total) * 100) : 0;
}

// Rate a currency converts at, or null when it should drop out of the
// combined view (design/FRONTEND.md §4 rule 1): the primary currency is always 1, any other
// currency needs a positive typed rate.
function rateFor(currencyId, primaryId, rates, locale) {
  if (currencyId === primaryId) return 1;
  const raw = parse(rates[currencyId], locale);
  const value = raw === null ? null : Number(raw);
  return value && value > 0 ? value : null;
}

function convert(amount, rate) {
  return Math.round(amount * rate * 100) / 100;
}

// Group totals across currencies: multiply each row by its currency's rate,
// round to two places, sum the rounded figures under their shared key — the
// one place the frontend adds two amounts (rule 1).
function combineGroup(stats, groupKey, rowKey, primaryId, rates, locale) {
  const totals = new Map();
  for (const stat of stats) {
    const rate = rateFor(stat.currency_id, primaryId, rates, locale);
    if (rate === null) continue;
    for (const row of stat[groupKey]) {
      const key = row[rowKey];
      totals.set(key, (totals.get(key) ?? 0) + convert(row.amount, rate));
    }
  }
  return totals;
}

function CombinedStats({ trip, stats, rates, locale }) {
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const countryName = (id) => trip.countries.find((c) => c.id === id)?.name || '';
  const countryFlag = (id) => trip.countries.find((c) => c.id === id)?.flag || '';
  const person = (id) => trip.people.find((p) => p.id === id);

  const total = stats.reduce((sum, stat) => {
    const rate = rateFor(stat.currency_id, primary.id, rates, locale);
    return rate === null ? sum : sum + convert(stat.total, rate);
  }, 0);

  const byLabel = [...combineGroup(stats, 'by_label', 'label', primary.id, rates, locale)]
    .sort((a, b) => b[1] - a[1]);
  const byCountry = [...combineGroup(stats, 'by_country', 'country_id', primary.id, rates, locale)]
    .sort((a, b) => b[1] - a[1]);
  const byPerson = combineGroup(stats, 'by_person', 'person_id', primary.id, rates, locale);

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between">
        <span class="fw-semibold">${t('stats.by_label')}</span>
        <b class="num">${t('stats.total', { amount: money(total, locale) })} ${primary.symbol}</b>
      </div>
      <ul class="list-group list-group-flush">
        ${byLabel.map(([label, amount]) => html`
          <li key=${label ?? ''} class="list-group-item">
            <div class="d-flex justify-content-between">
              ${label ? html`<${LabelBadge} name=${label} />` : html`<span class="text-body-secondary fst-italic">${t('stats.unlabelled')}</span>`}
              <span class="num">${money(amount, locale)} ${primary.symbol} <small class="text-body-secondary">${pct(amount, total)}%</small></span>
            </div>
            <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${pct(amount, total)}%"></div></div>
          </li>
        `)}
      </ul>
      <div class="card-body pt-2">
        <div class="alert alert-secondary py-2 px-3 small mb-0">${t('stats.overlap_note')} ${t('stats.combined_note')}</div>
      </div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('stats.by_country')}</div>
      <ul class="list-group list-group-flush">
        ${byCountry.map(([countryId, amount]) => html`
          <li key=${countryId} class="list-group-item">
            <div class="d-flex justify-content-between">
              <span>${countryFlag(countryId)} ${countryName(countryId)}</span>
              <span class="num">${money(amount, locale)} ${primary.symbol} <small class="text-body-secondary">${pct(amount, total)}%</small></span>
            </div>
            <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${pct(amount, total)}%"></div></div>
          </li>
        `)}
      </ul>
    </div>

    <div class="card shadow-sm">
      <div class="card-header fw-semibold">${t('stats.by_person')} <small class="text-body-secondary fw-normal">${t('stats.by_person_note')}</small></div>
      <ul class="list-group list-group-flush">
        ${trip.people.filter((p) => byPerson.has(p.id)).map((p) => html`
          <li key=${p.id} class="list-group-item d-flex justify-content-between">
            <span>${p.name}${p.default_weight !== '1' && html`<small class="text-body-secondary"> ${p.default_weight} ${t('stats.share')}</small>`}</span>
            <span class="num">${money(byPerson.get(p.id), locale)} ${primary.symbol}</span>
          </li>
        `)}
      </ul>
    </div>
  `;
}

function RatesCard({ trip, rates, onRateChange }) {
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const others = trip.currencies.filter((c) => c.id !== primary.id);

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('stats.your_rates')} <small class="text-body-secondary fw-normal">${t('stats.rates_scope')}</small></div>
      <div class="card-body">
        <div class="row g-2 align-items-center mb-2">
          <div class="col-auto"><span class="badge text-bg-primary">${primary.code}</span></div>
          <div class="col"><small class="text-body-secondary">${t('stats.base_currency')}</small></div>
          <div class="col-4 col-sm-3"><input class="form-control form-control-sm num text-end" value="1" disabled /></div>
        </div>
        ${others.map((c) => html`
          <div key=${c.id} class="row g-2 align-items-center mb-2">
            <div class="col-auto"><span class="badge text-bg-primary">${c.code}</span></div>
            <div class="col"><small class="text-body-secondary">${t('stats.rate_prefix', { code: primary.code })}</small></div>
            <div class="col-4 col-sm-3">
              <input class="form-control form-control-sm num text-end" inputmode="decimal"
                     value=${rates[c.id] ?? ''} onChange=${(e) => onRateChange(c.id, e.target.value)} />
            </div>
          </div>
        `)}
        <div class="alert alert-primary py-2 px-3 small mt-3 mb-0">${t('stats.rates_note')}</div>
      </div>
    </div>
  `;
}

function CurrencyStats({ stat, trip, locale }) {
  const countryName = (id) => trip.countries.find((c) => c.id === id)?.name || '';
  const countryFlag = (id) => trip.countries.find((c) => c.id === id)?.flag || '';
  const person = (id) => trip.people.find((p) => p.id === id);

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header d-flex justify-content-between">
        <span class="fw-semibold">${t('stats.by_label')}</span>
        <b class="num">${t('stats.total', { amount: money(stat.total, locale) })} ${stat.currency_code}</b>
      </div>
      <ul class="list-group list-group-flush">
        ${stat.by_label.map((row) => html`
          <li key=${row.label ?? ''} class="list-group-item">
            <div class="d-flex justify-content-between">
              ${row.label ? html`<${LabelBadge} name=${row.label} />` : html`<span class="text-body-secondary fst-italic">${t('stats.unlabelled')}</span>`}
              <span class="num">${money(row.amount, locale)} ${stat.currency_code} <small class="text-body-secondary">${pct(row.amount, stat.total)}%</small></span>
            </div>
            <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${pct(row.amount, stat.total)}%"></div></div>
          </li>
        `)}
      </ul>
      <div class="card-body pt-2"><div class="alert alert-secondary py-2 px-3 small mb-0">${t('stats.overlap_note')}</div></div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('stats.by_country')}</div>
      <ul class="list-group list-group-flush">
        ${stat.by_country.map((row) => html`
          <li key=${row.country_id} class="list-group-item">
            <div class="d-flex justify-content-between">
              <span>${countryFlag(row.country_id)} ${countryName(row.country_id)}</span>
              <span class="num">${money(row.amount, locale)} ${stat.currency_code} <small class="text-body-secondary">${pct(row.amount, stat.total)}%</small></span>
            </div>
            <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${pct(row.amount, stat.total)}%"></div></div>
          </li>
        `)}
      </ul>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('stats.by_person')} <small class="text-body-secondary fw-normal">${t('stats.by_person_note')}</small></div>
      <ul class="list-group list-group-flush">
        ${stat.by_person.map((row) => html`
          <li key=${row.person_id} class="list-group-item d-flex justify-content-between">
            <span>${person(row.person_id)?.name}
              ${person(row.person_id)?.default_weight !== '1' && html`<small class="text-body-secondary"> ${person(row.person_id)?.default_weight} ${t('stats.share')}</small>`}
            </span>
            <span class="num">${money(row.amount, locale)} ${stat.currency_code}</span>
          </li>
        `)}
      </ul>
    </div>

    <div class="card shadow-sm">
      <div class="card-header fw-semibold">${t('stats.by_day')}</div>
      <ul class="list-group list-group-flush">
        ${stat.by_day.map((row) => html`
          <li key=${row.date} class="list-group-item d-flex justify-content-between">
            <span>${fmtDate(row.date, locale)}</span>
            <span class="num">${money(row.amount, locale)} ${stat.currency_code}</span>
          </li>
        `)}
      </ul>
    </div>
  `;
}

export function Stats() {
  const store = useStore();
  const locale = getLocale();
  const [rates, setRates] = useState(() => getRates(store.slug));

  useEffect(() => {
    if (!store.stats) reload('stats');
  }, [store.slug]);

  if (!store.stats) return html`<${Loading} />`;

  const trip = store.trip;
  const multiCurrency = trip.currencies.length > 1;

  function onRateChange(currencyId, value) {
    setRates(setRate(store.slug, currencyId, value));
  }

  return html`
    ${multiCurrency && html`
      <${RatesCard} trip=${trip} rates=${rates} onRateChange=${onRateChange} />
      <${CombinedStats} trip=${trip} stats=${store.stats} rates=${rates} locale=${locale} />
      <h2 class="h6 text-body-secondary mt-4 mb-2">${t('stats.per_currency')}</h2>
    `}
    ${store.stats.map((stat) => html`<${CurrencyStats} key=${stat.currency_id} stat=${stat} trip=${trip} locale=${locale} />`)}
  `;
}
