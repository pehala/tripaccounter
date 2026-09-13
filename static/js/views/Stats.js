import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { money, parse, date as fmtDate } from '../fmt.js';
import { getRatesState, setTargetCurrency, setRateValue } from '../rates.js';
import { LabelBadge } from '../components/LabelBadge.js';
import { Loading } from '../components/Loading.js';

const STAT_GROUPS = ['by_label', 'by_country', 'by_person', 'by_day'];

function pct(amount, total) {
  return total > 0 ? Math.round((amount / total) * 100) : 0;
}

// Rate a currency converts at, into whichever currency the Total is set to
// (`targetId` — any trip currency, not necessarily the primary): the target
// itself is always 1, any other currency needs a positive typed rate or the
// Total section refuses to compute anything (design/FRONTEND.md §4 rule 1 —
// the one place the frontend adds two amounts, and only once every operand
// is known).
function rateFor(currencyId, targetId, values, locale) {
  if (currencyId === targetId) return 1;
  const raw = parse(values[currencyId], locale);
  const value = raw === null ? null : Number(raw);
  return value && value > 0 ? value : null;
}

function convert(amount, rate) {
  return Math.round(amount * rate * 100) / 100;
}

// Only ever called once every currency has a confirmed rate (see `allRatesSet`
// in Stats()); `rate === null` here would mean an incomplete total, which the
// caller never allows to render.
function combineGroup(stats, groupKey, rowKey, targetId, values, locale) {
  const totals = new Map();
  for (const stat of stats) {
    const rate = rateFor(stat.currency_id, targetId, values, locale);
    if (rate === null) continue;
    for (const row of stat[groupKey]) {
      const key = row[rowKey];
      totals.set(key, (totals.get(key) ?? 0) + convert(row.amount, rate));
    }
  }
  return totals;
}

// The sidebar can't be plain <a href="#..."> links: location.hash IS the tab
// (Trip.js reads it as `items`/`balances`/`stats`/`setup`), so navigating the
// hash to a section id would blank the page instead of switching tabs.
// Scroll directly, no hash involved. `scroll-margin-top` (app.css) keeps the
// target clear of the sticky header instead of landing half-hidden under it.
function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// A sidebar sub-link jumps to a specific stat type, which is collapsed by
// default in the content column — scrolling there alone would land on a
// header that looks identical to its neighbors. Force that one section open
// first so the destination is unambiguous.
function scrollToSection(headingId, bodyId) {
  const body = document.getElementById(bodyId);
  if (body && !body.classList.contains('show') && window.bootstrap) {
    window.bootstrap.Collapse.getOrCreateInstance(body, { toggle: false }).show();
  }
  scrollToId(headingId);
}

// Same collapse idiom as SplitEditor.js: a plain Bootstrap button + `.collapse`
// div, no custom JS state. Collapsed by default (no `show`) so a currency with
// many stat types stays scannable; `summary` (if given) stays visible even
// while collapsed.
function StatSection({ currencyId, group, icon, title, summary, children }) {
  const headingId = `stat-${currencyId}-${group}`;
  const bodyId = `${headingId}-body`;

  return html`
    <div id=${headingId} class="border rounded mb-2">
      <button class="btn btn-sm w-100 text-start d-flex align-items-center gap-2 py-2" type="button"
              data-bs-toggle="collapse" data-bs-target="#${bodyId}">
        <i class="bi ${icon}"></i>
        <span class="fw-semibold">${title}</span>
        ${summary && html`<span class="text-body-secondary ms-auto small">${summary}</span>`}
        <i class="bi bi-chevron-down"></i>
      </button>
      <div class="collapse" id=${bodyId}>
        <div class="px-3 pb-3 border-top pt-2">${children}</div>
      </div>
    </div>
  `;
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
        <${StatSection} currencyId=${id} group="by_label" icon="bi-tags" title=${t('stats.by_label')}>
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

        <${StatSection} currencyId=${id} group="by_country" icon="bi-geo-alt" title=${t('stats.by_country')}>
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

        <${StatSection} currencyId=${id} group="by_person" icon="bi-people" title=${t('stats.by_person')} summary=${t('stats.by_person_note')}>
          <ul class="list-group list-group-flush">
            ${trip.people.filter((p) => byPerson.has(p.id)).map((p) => html`
              <li key=${p.id} class="list-group-item d-flex justify-content-between">
                <span>${p.name}${p.default_weight !== '1' && html`<small class="text-body-secondary"> ${p.default_weight} ${t('stats.share')}</small>`}</span>
                <span class="num">${money(byPerson.get(p.id), locale)} ${code}</span>
              </li>
            `)}
          </ul>
        <//>

        <${StatSection} currencyId=${id} group="by_day" icon="bi-calendar3" title=${t('stats.by_day')}>
          <ul class="list-group list-group-flush">
            ${byDay.map((row) => html`
              <li key=${row.date} class="list-group-item d-flex justify-content-between">
                <span>${fmtDate(row.date, locale)}</span>
                <span class="num">${money(row.amount, locale)} ${code}</span>
              </li>
            `)}
          </ul>
        <//>
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

// `target` is whichever currency the user picked to convert everything into
// — any trip currency, not necessarily the primary. Every other currency
// needs its own typed rate into `target`.
function RatesForm({ trip, target, values, onTargetChange, onRateChange }) {
  const others = trip.currencies.filter((c) => c.id !== target.id);

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold">${t('stats.your_rates')} <small class="text-body-secondary fw-normal">${t('stats.rates_scope')}</small></div>
      <div class="card-body">
        <div class="row g-2 align-items-center mb-3">
          <div class="col-auto"><label class="col-form-label col-form-label-sm" for="stats-convert-to">${t('stats.convert_to')}</label></div>
          <div class="col-auto">
            <select id="stats-convert-to" class="form-select form-select-sm" value=${target.id}
                    onChange=${(e) => onTargetChange(Number(e.target.value))}>
              ${trip.currencies.map((c) => html`<option key=${c.id} value=${c.id}>${c.code}</option>`)}
            </select>
          </div>
        </div>
        ${others.map((c) => html`
          <div key=${c.id} class="row g-2 align-items-center mb-2">
            <div class="col-auto"><span class="badge text-bg-primary">1 ${c.code}</span></div>
            <div class="col-auto text-body-secondary">=</div>
            <div class="col-4 col-sm-3">
              <input class="form-control form-control-sm num text-end" inputmode="decimal"
                     value=${values[c.id] ?? ''} onChange=${(e) => onRateChange(c.id, e.target.value)} />
            </div>
            <div class="col-auto"><span class="badge text-bg-secondary">${target.code}</span></div>
          </div>
        `)}
        <div class="alert alert-primary py-2 px-3 small mt-3 mb-0">${t('stats.rates_note')}</div>
      </div>
    </div>
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
    ${!allRatesSet && html`<div class="alert alert-secondary py-2 px-3 small mb-0">${t('stats.rates_missing')}</div>`}
    ${allRatesSet && html`<div class="small text-body-secondary mb-2">${t('stats.total_note')}</div>`}
  `;

  return html`
    <${StatBlock} id="total" badgeLabel=${t('stats.total_tab')} code=${target.code} total=${total}
                  byLabel=${byLabel} byCountry=${byCountry} byPerson=${byPerson} byDay=${byDay}
                  trip=${trip} locale=${locale} extra=${extra} showSections=${allRatesSet} />
  `;
}

// One collapsible card per currency (or Total) in the sidebar: the badge
// scrolls straight to that section; the chevron is a separate toggle for its
// four stat-type sub-links; each sub-link opens that exact stat section in
// the content column before scrolling to it. Same bordered-card idiom as
// StatSection/SplitEditor above — a plain `.list-group` nested inside a
// `.list-group-item` mis-renders its border past the first collapsed entry,
// so this sidebar deliberately does not use Bootstrap's list-group at all.
function NavEntry({ id, label }) {
  const bodyId = `nav-${id}-body`;

  return html`
    <div class="border rounded mb-2">
      <div class="d-flex align-items-stretch">
        <button type="button" class="btn flex-grow-1 text-start d-flex align-items-center px-3 py-2"
                onClick=${() => scrollToId(`cur-${id}`)}>
          <span class="badge text-bg-primary">${label}</span>
        </button>
        <button type="button" class="btn px-2" data-bs-toggle="collapse" data-bs-target="#${bodyId}"
                aria-label=${t('stats.toggle_section')}>
          <i class="bi bi-chevron-down"></i>
        </button>
      </div>
      <div class="collapse" id=${bodyId}>
        <div class="d-flex flex-column border-top py-1">
          ${STAT_GROUPS.map((g) => html`
            <button key=${g} type="button" class="btn text-start ps-4 py-1 small"
                    onClick=${() => scrollToSection(`stat-${id}-${g}`, `stat-${id}-${g}-body`)}>${t(`stats.${g}`)}</button>
          `)}
        </div>
      </div>
    </div>
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

  return html`
    <div class="d-md-none sticky-top stats-nav-mobile mb-2 bg-body-tertiary py-1">
      <div class="nav nav-pills flex-row flex-nowrap overflow-x-auto gap-1">
        ${multiCurrency && html`
          <button type="button" class="nav-link text-nowrap border-0 bg-transparent"
                  onClick=${() => scrollToId('cur-total')}>
            <span class="badge text-bg-primary">${t('stats.total_tab')}</span>
          </button>
        `}
        ${store.stats.map((stat) => html`
          <button key=${stat.currency_id} type="button" class="nav-link text-nowrap border-0 bg-transparent"
                  onClick=${() => scrollToId(`cur-${stat.currency_id}`)}>
            <span class="badge text-bg-primary">${stat.currency_code}</span>
          </button>
        `)}
      </div>
    </div>
    <div class="row g-3">
      <div class="d-none d-md-block col-md-4 col-lg-3">
        <nav class="stats-nav" aria-label=${t('stats.jump_to')}>
          ${multiCurrency && html`<${NavEntry} id="total" label=${t('stats.total_tab')} />`}
          ${store.stats.map((stat) => html`<${NavEntry} key=${stat.currency_id} id=${stat.currency_id} label=${stat.currency_code} />`)}
        </nav>
      </div>
      <div class="col-md-8 col-lg-9 stats-content">
        ${multiCurrency && html`<${TotalBlock} stats=${store.stats} trip=${trip} ratesState=${ratesState} onTargetChange=${onTargetChange} onRateChange=${onRateChange} locale=${locale} />`}
        ${store.stats.map((stat) => html`<${CurrencyBlock} key=${stat.currency_id} stat=${stat} trip=${trip} locale=${locale} />`)}
      </div>
    </div>
  `;
}
