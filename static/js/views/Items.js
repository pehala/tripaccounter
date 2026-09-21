import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { DayGroup } from '../components/DayGroup.js';
import { ItemModal } from '../components/ItemModal.js';
import { Loading } from '../components/Loading.js';

// Items and transfers merge into one feed, newest first; on an exact tie an
// item sorts before a transfer, then by id descending (design/WALLETS.md §2
// "One fetch for the feed" - ordering rows by timestamp is not money
// arithmetic, so it is allowed client-side).
function mergeFeed(items, transfers) {
  const entries = [
    ...items.map((row) => ({ kind: 'item', row })),
    ...transfers.map((row) => ({ kind: 'transfer', row })),
  ];
  entries.sort((a, b) => {
    if (a.row.occurred_at !== b.row.occurred_at) {
      return a.row.occurred_at < b.row.occurred_at ? 1 : -1;
    }
    if (a.kind !== b.kind) return a.kind === 'item' ? -1 : 1;
    return b.row.id - a.row.id;
  });
  return entries;
}

// Entries older than the trip's start date collapse into one "Before the
// trip" group instead of a group per day; entries sort newest first, so once
// that boundary is crossed everything after it belongs there too.
function groupByDay(entries, startDate) {
  const groups = [];
  let current = null;
  for (const entry of entries) {
    const day = entry.row.occurred_at.slice(0, 10);
    const key = startDate && day < startDate ? 'before' : day;
    if (!current || current.date !== key) {
      current = { date: key, beforeTrip: key === 'before', entries: [] };
      groups.push(current);
    }
    current.entries.push(entry);
  }
  return groups;
}

function matches(entry, needle, walletName) {
  if (entry.kind === 'item') {
    const item = entry.row;
    return item.name.toLowerCase().includes(needle) || item.labels.some((l) => l.includes(needle));
  }
  const transfer = entry.row;
  const note = (transfer.note || '').toLowerCase();
  const fromName = (walletName(transfer.from_wallet_id) || '').toLowerCase();
  const toName = (walletName(transfer.to_wallet_id) || '').toLowerCase();
  return note.includes(needle) || fromName.includes(needle) || toName.includes(needle);
}

export function Items() {
  const store = useStore();
  const [filter, setFilter] = useState('');
  const [modalEntry, setModalEntry] = useState(undefined); // undefined = closed, null = new, {kind,row} = edit
  const locale = getLocale();

  useEffect(() => {
    if (!store.items) reload('items');
    if (!store.labels) reload('labels');
  }, [store.slug]);

  if (!store.items) return html`<${Loading} />`;

  const walletName = (id) => (store.trip.wallets || []).find((w) => w.id === id)?.name;
  const needle = filter.trim().toLowerCase();
  const feed = mergeFeed(store.items, store.transfers || []);
  const filtered = needle ? feed.filter((entry) => matches(entry, needle, walletName)) : feed;
  const groups = groupByDay(filtered, store.trip.start_date);
  // day_totals/before_trip_totals cover every item for their bucket; once a
  // filter hides some of them the total no longer matches what's on screen,
  // so don't show it.
  const totalsByDay = needle
    ? {}
    : Object.fromEntries((store.dayTotals || []).map((day) => [day.date, day.totals]));
  const beforeTripTotals = needle ? [] : store.beforeTripTotals || [];

  return html`
    <div class="d-flex align-items-center gap-2 mb-3">
      <button class="btn btn-primary px-4 d-none d-md-inline-block" onClick=${() => setModalEntry(null)}>
        <i class="bi bi-plus-lg"></i> ${t('items.add')}</button>
      <div class="input-group input-group-sm ms-auto" style="max-width:16rem">
        <span class="input-group-text bg-body"><i class="bi bi-search"></i></span>
        <input class="form-control" placeholder=${t('items.filter_placeholder')}
               value=${filter} onInput=${(e) => setFilter(e.target.value)} />
      </div>
    </div>
    ${groups.length === 0 && html`<p class="text-body-secondary">${t('items.empty')}</p>`}
    ${groups.map((group) => html`
      <${DayGroup} key=${group.date} date=${group.date} beforeTrip=${group.beforeTrip}
                   entries=${group.entries}
                   totals=${group.beforeTrip ? beforeTripTotals : totalsByDay[group.date]}
                   trip=${store.trip} locale=${locale} onSelect=${(entry) => setModalEntry(entry)} />
    `)}

    <button class="btn btn-primary btn-lg rounded-pill fab" aria-label=${t('items.add_expense')}
            onClick=${() => setModalEntry(null)}>
      <i class="bi bi-plus-lg"></i></button>

    ${modalEntry !== undefined && html`
      <${ItemModal} trip=${store.trip} labels=${store.labels || []} entry=${modalEntry}
                    onClose=${() => setModalEntry(undefined)} />
    `}
  `;
}
