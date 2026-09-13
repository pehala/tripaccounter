import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { DayGroup } from '../components/DayGroup.js';
import { ItemModal } from '../components/ItemModal.js';
import { Loading } from '../components/Loading.js';

function groupByDay(items) {
  const groups = [];
  let current = null;
  for (const item of items) {
    const day = item.occurred_at.slice(0, 10);
    if (!current || current.date !== day) {
      current = { date: day, items: [] };
      groups.push(current);
    }
    current.items.push(item);
  }
  return groups;
}

export function Items() {
  const store = useStore();
  const [filter, setFilter] = useState('');
  const [modalItem, setModalItem] = useState(undefined); // undefined = closed, null = new, object = edit
  const locale = getLocale();

  useEffect(() => {
    if (!store.items) reload('items');
    if (!store.labels) reload('labels');
  }, [store.slug]);

  if (!store.items) return html`<${Loading} />`;

  const items = store.items;
  const needle = filter.trim().toLowerCase();
  const filtered = needle
    ? items.filter((item) => item.name.toLowerCase().includes(needle) || item.labels.some((l) => l.includes(needle)))
    : items;
  const groups = groupByDay(filtered);
  // day_totals covers every item for the day; once a filter hides some of them
  // the total no longer matches what's on screen, so don't show it.
  const totalsByDay = needle
    ? {}
    : Object.fromEntries((store.dayTotals || []).map((day) => [day.date, day.totals]));

  return html`
    <div class="d-flex align-items-center gap-2 mb-3">
      <button class="btn btn-primary px-4 d-none d-md-inline-block" onClick=${() => setModalItem(null)}>
        <i class="bi bi-plus-lg"></i> ${t('items.add')}</button>
      <div class="input-group input-group-sm ms-auto" style="max-width:16rem">
        <span class="input-group-text bg-body"><i class="bi bi-search"></i></span>
        <input class="form-control" placeholder=${t('items.filter_placeholder')}
               value=${filter} onInput=${(e) => setFilter(e.target.value)} />
      </div>
    </div>
    ${groups.length === 0 && html`<p class="text-body-secondary">${t('items.empty')}</p>`}
    ${groups.map((group) => html`
      <${DayGroup} key=${group.date} date=${group.date} items=${group.items} totals=${totalsByDay[group.date]}
                   trip=${store.trip} locale=${locale} onSelect=${(item) => setModalItem(item)} />
    `)}

    <button class="btn btn-primary btn-lg rounded-pill fab" onClick=${() => setModalItem(null)}>
      <i class="bi bi-plus-lg"></i></button>

    ${modalItem !== undefined && html`
      <${ItemModal} trip=${store.trip} labels=${store.labels || []} item=${modalItem}
                    onClose=${() => setModalItem(undefined)} />
    `}
  `;
}
