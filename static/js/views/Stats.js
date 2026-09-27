import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload, setStatsDims } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { money, date as fmtDate } from '../fmt.js';
import { getRatesState, setTargetCurrency, setRateValue } from '../rates.js';
import { getDims, setDims, getShownCurrency, setShownCurrency, getView, setView } from '../breakdown.js';
import { rateFor, convert, combineRows } from '../convert.js';
import { isBeforeTrip } from '../days.js';
import { LabelBadge } from '../components/LabelBadge.js';
import { Loading } from '../components/Loading.js';
import { RatesForm } from '../components/RatesForm.js';
import { StatsChart } from '../components/StatsChart.js';

// Every dimension the picker offers, in its order, mapped to the key it answers
// under in a row (design/STATS.md §2). `currency` is deliberately absent: the
// server groups by it whatever is asked for, so it is never a choice.
const DIMENSIONS = {
  day: 'date',
  person: 'person_id',
  payer: 'payer_id',
  label: 'label',
  country: 'country_id',
  city: 'city',
  wallet: 'wallet_id',
};

function pct(amount, whole) {
  return whole > 0 ? Math.round((amount / whole) * 100) : 0;
}

// The chain a grouping covers, minus the leading `currency` the server always
// adds — so a grouping is addressed by the dimensions the user actually picked.
function chainOf(group) {
  return group.by.slice(1).join('|');
}

// Every day before the trip folds into one `date: null` row per remaining key set,
// the item feed's "Before the trip" group. The server groups by real day only, so
// this is the one place the page adds amounts outside the Total — the rows it merges
// sit where the first of them did, which keeps the bucket ahead of the trip's days.
function foldBeforeTrip(rows, startDate) {
  const merged = new Map();
  for (const row of rows) {
    const keys = isBeforeTrip(row.keys.date, startDate) ? { ...row.keys, date: null } : row.keys;
    const id = JSON.stringify(keys);
    const previous = merged.get(id);
    merged.set(id, previous
      ? { keys, amount: previous.amount + row.amount, item_count: previous.item_count + row.item_count }
      : { ...row, keys });
  }
  return [...merged.values()];
}

// Index one page section's rows by chain: a currency's own (filtered to it, its
// `currency_id` dropped) or the Total's (converted and combined across them).
function indexRows(groups, pick, startDate) {
  return new Map(groups.map((group) => {
    const rows = pick(group.rows);
    return [chainOf(group), group.by.includes('day') ? foldBeforeTrip(rows, startDate) : rows];
  }));
}

function forCurrency(currencyId) {
  return (rows) => rows
    .filter((row) => row.keys.currency_id === currencyId)
    .map(({ keys: { currency_id, ...keys }, ...row }) => ({ ...row, keys }));
}

// A row belongs under a parent when it agrees on every key the parent has.
function under(rows, parentKeys) {
  return rows.filter((row) => Object.entries(parentKeys).every(([k, v]) => row.keys[k] === v));
}

// Each level's own figure is another grouping's row — the server answered the
// chain's prefixes for exactly this, and nothing here ever adds two amounts
// together (design/FRONTEND.md §4 rule 1).
function buildNodes(index, dims, depth, parentKeys) {
  const rows = index.get(dims.slice(0, depth + 1).join('|')) ?? [];
  return under(rows, parentKeys).map((row) => ({
    dim: dims[depth],
    row,
    children: depth + 1 < dims.length ? buildNodes(index, dims, depth + 1, row.keys) : [],
  }));
}

function KeyLabel({ dim, row, trip }) {
  const value = row.keys[DIMENSIONS[dim]];
  const muted = (text) => html`<span class="text-body-secondary fst-italic">${text}</span>`;

  if (dim === 'label') return value === null ? muted(t('stats.unlabelled')) : html`<${LabelBadge} name=${value} />`;
  if (dim === 'city' && value === null) return muted(t('stats.unset'));
  if (dim === 'wallet') {
    const wallet = trip.wallets.find((w) => w.id === value);
    const owner = trip.people.find((p) => p.id === wallet?.person_id);
    return html`<span>${wallet?.name} <small class="text-body-secondary">${owner?.name}</small></span>`;
  }
  const person = dim === 'person' && trip.people.find((p) => p.id === value);
  return html`
    <span>${keyText(dim, value, trip, getLocale())}${person && person.default_weight !== '1'
      && html`<small class="text-body-secondary"> ${person.default_weight} ${t('stats.share')}</small>`}</span>
  `;
}

// A key as plain text: a chart's axis and legend, and the text inside KeyLabel.
function keyText(dim, value, trip, locale) {
  if (dim === 'label') return value ?? t('stats.unlabelled');
  if (dim === 'country') {
    const country = trip.countries.find((c) => c.id === value);
    return `${country?.flag} ${country?.name}`;
  }
  if (dim === 'person' || dim === 'payer') return trip.people.find((p) => p.id === value)?.name;
  if (dim === 'wallet') {
    const wallet = trip.wallets.find((w) => w.id === value);
    const owner = trip.people.find((p) => p.id === wallet?.person_id);
    return `${wallet?.name} · ${owner?.name}`;
  }
  if (dim === 'day') return value === null ? t('day.before_trip') : fmtDate(value, locale);
  return value ?? t('stats.unset');
}

// A person keeps their own roster colour in a chart; anything else takes the palette's.
function keyColor(dim, value, trip) {
  if (dim !== 'person' && dim !== 'payer') return null;
  return trip.people.find((p) => p.id === value)?.color ?? null;
}

// The before-trip bucket (`date: null`) if any row has it, then every trip day up
// to the last day with spend, plus any row's day after the trip, so a day with no
// spend is an empty slot on the axis rather than missing from it — and a trip still
// under way ends at its last expense, not its end date.
function axisDays(trip, rows) {
  const days = new Set(rows.map((row) => row.keys.date).filter((day) => day !== null));
  const spent = [...days].sort().at(-1);
  const final = [trip.end_date, spent].filter(Boolean).sort()[0];
  if (trip.start_date && spent) {
    const last = new Date(`${final}T00:00:00Z`);
    for (const day = new Date(`${trip.start_date}T00:00:00Z`); day <= last; day.setUTCDate(day.getUTCDate() + 1)) {
      days.add(day.toISOString().slice(0, 10));
    }
  }
  const before = rows.some((row) => row.keys.date === null) ? [null] : [];
  return [...before, ...[...days].sort()];
}

// What the chart draws, from the same index the list renders, by two rules for any
// chain: the first dimension is the axis — vertical columns for `day`, horizontal
// bars otherwise — and every later one splits each bar into a series per combination
// of their values, read off the deepest grouping; stacked unless one of them is
// `label`, whose overlapping rows stand side by side.
function chartSpec(index, dims, trip, locale) {
  const [first, ...later] = dims;
  const field = DIMENSIONS[first];
  const top = index.get(first) ?? [];
  const categories = first === 'day' ? axisDays(trip, top) : top.map((row) => row.keys[field]);
  const amountsOf = (rows) => categories.map(
    (category) => rows.find((row) => row.keys[field] === category)?.amount ?? null);
  const leaves = later.length ? index.get(dims.join('|')) ?? [] : [];
  const seriesKeys = (keys) => Object.fromEntries(later.map((dim) => [DIMENSIONS[dim], keys[DIMENSIONS[dim]]]));
  const combos = [...new Map(leaves.map((row) => [JSON.stringify(seriesKeys(row.keys)), seriesKeys(row.keys)])).values()];

  return {
    horizontal: first !== 'day',
    stacked: !later.includes('label'),
    labels: categories.map((value) => keyText(first, value, trip, locale)),
    series: later.length
      ? combos.map((keys) => ({
        label: later.map((dim) => keyText(dim, keys[DIMENSIONS[dim]], trip, locale)).join(' · '),
        color: later.length === 1 ? keyColor(later[0], keys[DIMENSIONS[later[0]]], trip) : null,
        data: amountsOf(under(leaves, keys)),
      }))
      : [{ label: null, color: null, data: amountsOf(top) }],
  };
}

// `parentTotal` is the row this one sits inside — the currency's total at the top
// level, its own parent's amount below that — so a share reads against what it is
// a part of. A second-level 29% means 29% of that day, not of the whole trip.
function BreakdownNode({ node, parentTotal, code, trip, locale }) {
  const share = pct(node.row.amount, parentTotal);

  return html`
    <li class="list-group-item">
      <div class="d-flex justify-content-between gap-2">
        <${KeyLabel} dim=${node.dim} row=${node.row} trip=${trip} />
        <span class="num text-nowrap">${money(node.row.amount, locale)} ${code} <small class="text-body-secondary">${share}%</small></span>
      </div>
      <div class="progress mt-1" style="height:.35rem"><div class="progress-bar" style="width:${share}%"></div></div>
      ${node.children.length > 0 && html`
        <ul class="list-group list-group-flush ms-3 mt-1">
          ${node.children.map((child) => html`
            <${BreakdownNode} key=${JSON.stringify(child.row.keys)} node=${child} parentTotal=${node.row.amount}
                              code=${code} trip=${trip} locale=${locale} />
          `)}
        </ul>
      `}
    </li>
  `;
}

// Shared renderer for a currency's own breakdown *or* the Total's converted
// one — both normalize to the same index before calling in, so the tree isn't
// written once per currency and again for the Total.
function StatSection({ id, code, badgeLabel = code, index, dims, trip, locale, view, extra, showRows = true }) {
  const total = (index.get('') ?? [])[0]?.amount ?? null;
  const chart = showRows && view === 'chart' && dims.length > 0;
  const nodes = showRows && !chart ? buildNodes(index, dims, 0, {}) : [];

  return html`
    <section id="cur-${id}" class="mb-4 scroll-anchor">
      <h2 class="h6 d-flex align-items-center gap-2 pt-2">
        <span class="badge text-bg-primary">${badgeLabel}</span>
        ${total !== null && html`<b class="num">${t('stats.total', { amount: money(total, locale) })} ${code}</b>`}
      </h2>

      ${extra}

      ${showRows && html`
        <div id="breakdown-${id}">
          ${dims.includes('person') && html`<div class="small text-body-secondary mb-1">${t('stats.by_person_note')}</div>`}
          ${chart
            ? html`<${StatsChart} spec=${chartSpec(index, dims, trip, locale)} code=${code} locale=${locale} />`
            : html`
              <ul class="list-group list-group-flush">
                ${nodes.map((node) => html`
                  <${BreakdownNode} key=${JSON.stringify(node.row.keys)} node=${node} parentTotal=${total}
                                    code=${code} trip=${trip} locale=${locale} />
                `)}
              </ul>
            `}
          ${dims.includes('label') && html`<div class="alert alert-secondary py-2 px-3 small mt-2 mb-0">${t('stats.overlap_note')}</div>`}
        </div>
      `}
    </section>
  `;
}

// Which currency's section is on screen, and the chain it is grouped by. The
// currency is a filter over rows already in the store — every grouping carries
// every currency — so changing it costs no request, unlike changing the chain.
function StatsPicker({ shown, options, onShownChange, dims, onDimsChange, view, onViewChange }) {
  const available = Object.keys(DIMENSIONS).filter((dim) => !dims.includes(dim));

  return html`
    <div class="card shadow-sm mb-3">
      <div class="card-header fw-semibold d-flex align-items-center justify-content-between">
        ${t('stats.breakdown')}
        <div class="btn-group btn-group-sm" role="group">
          ${['list', 'chart'].map((option) => html`
            <button key=${option} type="button" aria-pressed=${option === view}
                    class="btn ${option === view ? 'btn-secondary' : 'btn-outline-secondary'}"
                    onClick=${() => onViewChange(option)}>
              <i class="bi ${option === 'list' ? 'bi-list-ul' : 'bi-bar-chart'}"></i> ${t(`stats.view.${option}`)}
            </button>
          `)}
        </div>
      </div>
      <div class="card-body">
        ${options.length > 1 && html`
          <div class="row g-2 align-items-center mb-3">
            <div class="col-auto"><label class="col-form-label col-form-label-sm" for="stats-currency">${t('stats.showing')}</label></div>
            <div class="col-auto">
              <select id="stats-currency" class="form-select form-select-sm" value=${String(shown)}
                      onChange=${(e) => onShownChange(e.target.value === 'total' ? 'total' : Number(e.target.value))}>
                ${options.map((option) => html`<option key=${option.id} value=${String(option.id)}>${option.label}</option>`)}
              </select>
            </div>
          </div>
        `}
        <div class="d-flex flex-wrap align-items-center gap-2">
          ${dims.map((dim, index) => html`
            <button key=${dim} type="button" class="btn btn-sm btn-primary d-flex align-items-center gap-1"
                    onClick=${() => onDimsChange(dims.filter((_, i) => i !== index))}>
              ${t(`stats.dim.${dim}`)} <i class="bi bi-x-lg"></i>
            </button>
          `)}
          ${available.length > 0 && html`
            <select id="stats-dimension" class="form-select form-select-sm w-auto" value=""
                    onChange=${(e) => e.target.value && onDimsChange([...dims, e.target.value])}>
              <option value="">${t('stats.add_dimension')}</option>
              ${available.map((dim) => html`<option key=${dim} value=${dim}>${t(`stats.dim.${dim}`)}</option>`)}
            </select>
          `}
        </div>
      </div>
    </div>
  `;
}

// Only renders rows once every currency has a confirmed rate (`allRatesSet`) —
// never a partial or misleading sum, just the rates form or the whole answer.
function TotalSection({ groups, dims, trip, ratesState, onTargetChange, onRateChange, locale, view }) {
  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const target = trip.currencies.find((c) => c.id === ratesState.target) || primary;
  const values = ratesState.values;

  const allRatesSet = trip.currencies.every((c) => rateFor(c.id, target.id, values, locale) !== null);
  const index = indexRows(groups, (rows) =>
    allRatesSet ? combineRows(rows, target.id, values, locale) : [], trip.start_date);

  const extra = html`
    <${RatesForm} trip=${trip} target=${target} values=${values} onTargetChange=${onTargetChange} onRateChange=${onRateChange} />
    ${!allRatesSet && html`<div class="alert alert-secondary py-2 px-3 small mb-0">${t('rates.missing')}</div>`}
    ${allRatesSet && html`<div class="small text-body-secondary mb-2">${t('rates.total_note')}</div>`}
  `;

  return html`
    <${StatSection} id="total" badgeLabel=${t('nav.total')} code=${target.code} index=${index}
                    dims=${dims} trip=${trip} locale=${locale} view=${view} extra=${extra} showRows=${allRatesSet} />
  `;
}

export function Stats() {
  const store = useStore();
  const locale = getLocale();
  const [ratesState, setRatesState] = useState(() => getRatesState(store.slug));
  const [shown, setShown] = useState(() => getShownCurrency(store.slug));
  const [view, setViewState] = useState(() => getView(store.slug));
  const dims = store.statsDims;

  useEffect(() => {
    if (!store.stats) reload('stats');
  }, [store.slug, store.stats]);

  if (!store.stats) return html`<${Loading} />`;

  const trip = store.trip;
  const multiCurrency = trip.currencies.length > 1;
  const totals = store.stats.find((group) => group.by.length === 1)?.rows ?? [];
  const spent = trip.currencies.filter((c) => totals.some((row) => row.keys.currency_id === c.id));
  const primary = spent.find((c) => c.is_primary) || spent[0];

  const options = [
    ...(multiCurrency ? [{ id: 'total', label: t('nav.total') }] : []),
    ...spent.map((currency) => ({ id: currency.id, label: currency.code })),
  ];
  // A remembered currency that this trip no longer spends falls back to the primary.
  const picked = options.some((option) => option.id === shown) ? shown : primary?.id;

  function onTargetChange(currencyId) {
    setRatesState(setTargetCurrency(store.slug, currencyId));
  }

  function onRateChange(currencyId, value) {
    setRatesState(setRateValue(store.slug, currencyId, value));
  }

  function onDimsChange(next) {
    setStatsDims(setDims(store.slug, next));
  }

  function onShownChange(next) {
    setShown(setShownCurrency(store.slug, next));
  }

  function onViewChange(next) {
    setViewState(setView(store.slug, next));
  }

  const currency = spent.find((c) => c.id === picked);

  return html`
    <div class="stats-content">
      <${StatsPicker} shown=${picked} options=${options} onShownChange=${onShownChange}
                      dims=${dims} onDimsChange=${onDimsChange} view=${view} onViewChange=${onViewChange} />
      ${picked === 'total' && html`
        <${TotalSection} groups=${store.stats} dims=${dims} trip=${trip} ratesState=${ratesState}
                         onTargetChange=${onTargetChange} onRateChange=${onRateChange} locale=${locale} view=${view} />
      `}
      ${currency && html`
        <${StatSection} id=${currency.id} code=${currency.code}
                        index=${indexRows(store.stats, forCurrency(currency.id), trip.start_date)}
                        dims=${dims} trip=${trip} locale=${locale} view=${view} />
      `}
    </div>
  `;
}
