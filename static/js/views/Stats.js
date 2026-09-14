import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { money, date as fmtDate } from '../fmt.js';
import { getRatesState, setTargetCurrency, setRateValue } from '../rates.js';
import { rateFor, convert, combineGroup } from '../convert.js';
import { LabelBadge } from '../components/LabelBadge.js';
import { Loading } from '../components/Loading.js';
import { CollapsibleSection } from '../components/CollapsibleSection.js';
import { RatesForm } from '../components/RatesForm.js';
import { SideNav, MobilePillNav } from '../components/SideNav.js';

const STAT_GROUPS = ['by_label', 'by_country', 'by_person', 'by_day'];

function pct(amount, total) {
  return total > 0 ? Math.round((amount / total) * 100) : 0;
}

// Single markup renderer for a currency's own stats *or* the Total's
// converted figures — both normalize into this same shape (byLabel/byCountry
// as {label|country_id, amount}[], byPerson as a person_id -> amount Map,
// byDay as {date, amount}[]) so the four stat sections are written once,
// instead of once per currency and again for the Total.
function StatBlock({ id, badgeLabel, code, total, byLabel, byCountry, byPerson, byDay, trip, locale, extra, showSections = true }) {
  const countryName = (cid) => trip.countries.find((c) => c.id === cid)?.name || '';
  const countryFlag = (cid) => trip.countries.find((c) => c.id === cid)?.flag || '';

  return html`
    <section id="cur-${id}" class="mb-4">
      <h2 class="h6 d-flex align-items-center gap-2 pt-2">
        <span class="badge text-bg-primary">${badgeLabel}</span>
        ${total !== null && html`<b class="num">${t('stats.total', { amount: money(total, locale) })} ${code}</b>`}
      </h2>

      ${extra}

      ${showSections && html`
        <div id="sec-accordion-${id}">
          <${CollapsibleSection} id="sec-${id}-by_label" parentId="sec-accordion-${id}" icon="bi-tags" title=${t('stats.by_label')}>
            <ul class="list-group list-group-flush">
              ${byLabel.map((row) => html`
                <li key=${row.label ?? ''} class="list-group-item">
                  <div class="d-flex justify-content-between">
                    ${row.label ? html`<${LabelBadge} name=${row.label} />` : html`<span class="text-body-secondary fst-italic">${t('stats.unlabelled')}</span>`}
                    <span class="num">${money(row.amount, locale)} ${code} <small class="text-body-secondary">${pct(row.amount, total)}%</small></span>
                  </div>
                  <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${pct(row.amount, total)}%"></div></div>
                </li>
              `)}
            </ul>
            <div class="alert alert-secondary py-2 px-3 small mt-2 mb-0">${t('stats.overlap_note')}</div>
          <//>

          <${CollapsibleSection} id="sec-${id}-by_country" parentId="sec-accordion-${id}" icon="bi-geo-alt" title=${t('stats.by_country')}>
            <ul class="list-group list-group-flush">
              ${byCountry.map((row) => html`
                <li key=${row.country_id} class="list-group-item">
                  <div class="d-flex justify-content-between">
                    <span>${countryFlag(row.country_id)} ${countryName(row.country_id)}</span>
                    <span class="num">${money(row.amount, locale)} ${code} <small class="text-body-secondary">${pct(row.amount, total)}%</small></span>
                  </div>
                  <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${pct(row.amount, total)}%"></div></div>
                </li>
              `)}
            </ul>
          <//>

          <${CollapsibleSection} id="sec-${id}-by_person" parentId="sec-accordion-${id}" icon="bi-people" title=${t('stats.by_person')} summary=${t('stats.by_person_note')}>
            <ul class="list-group list-group-flush">
              ${trip.people.filter((p) => byPerson.has(p.id)).map((p) => html`
                <li key=${p.id} class="list-group-item d-flex justify-content-between">
                  <span>${p.name}${p.default_weight !== '1' && html`<small class="text-body-secondary"> ${p.default_weight} ${t('stats.share')}</small>`}</span>
                  <span class="num">${money(byPerson.get(p.id), locale)} ${code}</span>
                </li>
              `)}
            </ul>
          <//>

          <${CollapsibleSection} id="sec-${id}-by_day" parentId="sec-accordion-${id}" icon="bi-calendar3" title=${t('stats.by_day')}>
            <ul class="list-group list-group-flush">
              ${byDay.map((row) => html`
                <li key=${row.date} class="list-group-item d-flex justify-content-between">
                  <span>${fmtDate(row.date, locale)}</span>
                  <span class="num">${money(row.amount, locale)} ${code}</span>
                </li>
              `)}
            </ul>
          <//>
        </div>
      `}
    </section>
  `;
}

function CurrencyBlock({ stat, trip, locale }) {
  const byPerson = new Map(stat.by_person.map((row) => [row.person_id, row.amount]));

  return html`
    <${StatBlock} id=${stat.currency_id} badgeLabel=${stat.currency_code} code=${stat.currency_code} total=${stat.total}
                  byLabel=${stat.by_label} byCountry=${stat.by_country} byPerson=${byPerson} byDay=${stat.by_day}
                  trip=${trip} locale=${locale} />
  `;
}

// The Total is another entry in the currency switcher, not a silent
// best-effort sum: it only renders once every currency has a confirmed rate
// into the chosen target (see `allRatesSet`), so there is never a partial or
// misleading figure on screen — just the form, or the whole answer. Its
// figures are normalized into the same shape `StatBlock` expects from a
// currency, so the four stat sections aren't written a second time here.
function TotalBlock({ stats, trip, ratesState, onTargetChange, onRateChange, locale }) {
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const target = trip.currencies.find((c) => c.id === ratesState.target) || primary;
  const values = ratesState.values;

  const allRatesSet = trip.currencies.every((c) => rateFor(c.id, target.id, values, locale) !== null);

  const total = allRatesSet
    ? stats.reduce((sum, stat) => sum + convert(stat.total, rateFor(stat.currency_id, target.id, values, locale)), 0)
    : null;
  const byLabel = allRatesSet
    ? [...combineGroup(stats, 'by_label', 'label', target.id, values, locale)]
        .sort((a, b) => b[1] - a[1])
        .map(([label, amount]) => ({ label, amount }))
    : [];
  const byCountry = allRatesSet
    ? [...combineGroup(stats, 'by_country', 'country_id', target.id, values, locale)]
        .sort((a, b) => b[1] - a[1])
        .map(([country_id, amount]) => ({ country_id, amount }))
    : [];
  const byPerson = allRatesSet ? combineGroup(stats, 'by_person', 'person_id', target.id, values, locale) : new Map();
  const byDay = allRatesSet
    ? [...combineGroup(stats, 'by_day', 'date', target.id, values, locale)]
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([date, amount]) => ({ date, amount }))
    : [];

  const extra = html`
    <${RatesForm} trip=${trip} target=${target} values=${values} onTargetChange=${onTargetChange} onRateChange=${onRateChange} />
    ${!allRatesSet && html`<div class="alert alert-secondary py-2 px-3 small mb-0">${t('rates.missing')}</div>`}
    ${allRatesSet && html`<div class="small text-body-secondary mb-2">${t('rates.total_note')}</div>`}
  `;

  return html`
    <${StatBlock} id="total" badgeLabel=${t('nav.total')} code=${target.code} total=${total}
                  byLabel=${byLabel} byCountry=${byCountry} byPerson=${byPerson} byDay=${byDay}
                  trip=${trip} locale=${locale} extra=${extra} showSections=${allRatesSet} />
  `;
}

export function Stats() {
  const store = useStore();
  const locale = getLocale();
  const [ratesState, setRatesState] = useState(() => getRatesState(store.slug));

  useEffect(() => {
    if (!store.stats) reload('stats');
  }, [store.slug]);

  if (!store.stats) return html`<${Loading} />`;

  const trip = store.trip;
  const multiCurrency = trip.currencies.length > 1;

  function onTargetChange(currencyId) {
    setRatesState(setTargetCurrency(store.slug, currencyId));
  }

  function onRateChange(currencyId, value) {
    setRatesState(setRateValue(store.slug, currencyId, value));
  }

  const groups = STAT_GROUPS.map((key) => ({ key, title: t(`stats.${key}`) }));
  const entries = [
    ...(multiCurrency ? [{ id: 'total', label: t('nav.total'), groups }] : []),
    ...store.stats.map((stat) => ({ id: stat.currency_id, label: stat.currency_code, groups })),
  ];

  return html`
    <${MobilePillNav} entries=${entries} />
    <div class="row g-3">
      <div class="d-none d-md-block col-md-4 col-lg-3">
        <${SideNav} entries=${entries} ariaLabel=${t('nav.jump_to')} />
      </div>
      <div class="col-md-8 col-lg-9 stats-content">
        ${multiCurrency && html`<${TotalBlock} stats=${store.stats} trip=${trip} ratesState=${ratesState} onTargetChange=${onTargetChange} onRateChange=${onRateChange} locale=${locale} />`}
        ${store.stats.map((stat) => html`<${CurrencyBlock} key=${stat.currency_id} stat=${stat} trip=${trip} locale=${locale} />`)}
      </div>
    </div>
  `;
}
