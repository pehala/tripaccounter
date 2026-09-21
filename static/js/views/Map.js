import { useEffect, useMemo, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { showCollapse } from '../collapse.js';
import { itemMatches } from '../filter.js';
import { t, getLocale } from '../i18n/index.js';
import { dateTime, money } from '../fmt.js';
import { Avatar } from '../components/Avatar.js';
import { CollapsibleSection } from '../components/CollapsibleSection.js';
import { ItemModal } from '../components/ItemModal.js';
import { Loading } from '../components/Loading.js';
import { MapCanvas } from '../components/MapCanvas.js';
import { MapFilters, NO_FILTERS } from '../components/MapFilters.js';

// The tab reads store.items and nothing else: coordinates ride along on every item
// the feed already loaded, so opening the map costs no call. Coordinates are optional,
// so an expense without them is simply not on the map, and the count line says so.
//
// The map grows to the bottom of the viewport (app.css, .map-page), so everything else
// - filters, the selected pin's expenses - sits above it, in one collapsible section:
// folding it away is how the map gets the whole page. The count line is the section's
// own summary, so it stays readable while folded.

const CONTROLS = 'map-controls';

function placedItems(items) {
  return items.filter((item) => item.lat && item.lon);
}

function keep(item, filters) {
  const needle = filters.needle.trim().toLowerCase();
  if (needle && !itemMatches(item, needle)) return false;
  if (filters.labels.length > 0 && !item.labels.some((name) => filters.labels.includes(name))) {
    return false;
  }
  const day = item.occurred_at.slice(0, 10);
  if (filters.from && day < filters.from) return false;
  if (filters.to && day > filters.to) return false;
  return true;
}

// Two expenses at one restaurant are one pin: grouped on the coordinate pair exactly
// as it arrived, never on a rounded copy of it.
function groupByCoordinate(items) {
  const byKey = {};
  const order = [];
  for (const item of items) {
    const key = `${item.lat},${item.lon}`;
    if (!byKey[key]) {
      byKey[key] = { key, lat: Number(item.lat), lon: Number(item.lon), items: [] };
      order.push(key);
    }
    byKey[key].items.push(item);
  }
  return order.map((key) => byKey[key]);
}

export function Map() {
  const store = useStore();
  const [filters, setFilters] = useState(NO_FILTERS);
  const [selectedKey, setSelectedKey] = useState(null);
  const [focus, setFocus] = useState(null);
  const [folds, setFolds] = useState(0);
  const [modalEntry, setModalEntry] = useState(undefined); // undefined = closed, {kind,row} = edit
  const locale = getLocale();

  useEffect(() => {
    if (!store.items) reload('items');
    if (!store.labels) reload('labels');
  }, [store.slug]);

  // Picking a pin whose expenses are folded away would show nothing, so the section
  // opens itself; Bootstrap animates it, and Leaflet is told once it has settled.
  useEffect(() => {
    if (selectedKey) showCollapse(`${CONTROLS}-body`);
  }, [selectedKey]);

  useEffect(() => {
    const body = document.getElementById(`${CONTROLS}-body`);
    if (!body) return;
    const settled = () => setFolds((n) => n + 1);
    body.addEventListener('shown.bs.collapse', settled);
    body.addEventListener('hidden.bs.collapse', settled);
    return () => {
      body.removeEventListener('shown.bs.collapse', settled);
      body.removeEventListener('hidden.bs.collapse', settled);
    };
  }, [store.items]);

  const placed = useMemo(() => placedItems(store.items || []), [store.items]);
  const points = useMemo(
    () => groupByCoordinate(placed.filter((item) => keep(item, filters))),
    [placed, filters],
  );

  if (!store.items) return html`<${Loading} />`;
  if (placed.length === 0) return html`<p class="text-body-secondary">${t('map.empty')}</p>`;

  const shown = points.reduce((count, point) => count + point.items.length, 0);
  const selected = points.find((point) => point.key === selectedKey) || null;
  const head = selected?.items[0];
  const payerOf = (item) => store.trip.people.find((person) => person.id === item.payer_id);

  return html`
    <div class="map-page d-flex flex-column flex-grow-1">
      <${CollapsibleSection} id=${CONTROLS} icon="bi-funnel" title=${t('map.controls')}
                             defaultOpen=${true}
                             summary=${t('map.placed', { n: shown, total: store.items.length })}>
        <${MapFilters} filters=${filters} labels=${[...new Set(placed.flatMap((item) => item.labels))].sort()}
                       onChange=${(patch) => setFilters((current) => ({ ...current, ...patch }))} />

        ${shown === 0 && html`<p class="text-body-secondary mb-0">${t('map.no_matches')}</p>`}

        ${selected && html`
          <div class="card shadow-sm">
            <div class="card-header d-flex align-items-center gap-2 py-1">
              <i class="bi bi-geo-alt-fill text-primary"></i>
              <span class="fw-semibold">${head.city || `${head.lat}, ${head.lon}`}</span>
              <button type="button" class="btn btn-sm btn-link ms-auto py-0" aria-label=${t('map.zoom')}
                      onClick=${() => setFocus({ key: selected.key, at: Date.now() })}>
                <i class="bi bi-zoom-in"></i></button>
              <button type="button" class="btn-close" aria-label=${t('map.close')}
                      onClick=${() => setSelectedKey(null)}></button>
            </div>
            <div class="list-group list-group-flush item-list">
              ${selected.items.map((item) => html`
                <button key=${item.id} type="button"
                        class="list-group-item list-group-item-action d-flex gap-3 text-start"
                        onClick=${() => setModalEntry({ kind: 'item', row: item })}>
                  <span class="flex-grow-1 min-w-0">
                    <span class="d-block fw-semibold item-line">${item.name}</span>
                    <small class="text-body-secondary d-block item-line">${dateTime(item.occurred_at, locale)} · <${Avatar} person=${payerOf(item)} /> ${t('items.paid_by', { name: payerOf(item)?.name || '' })}</small>
                  </span>
                  <span class="text-end num text-nowrap fw-semibold">
                    ${money(item.amount, locale)} ${item.currency_code}
                  </span>
                </button>
              `)}
            </div>
          </div>`}
      <//>

      <${MapCanvas} points=${points} selectedKey=${selectedKey} focus=${focus} onSelect=${setSelectedKey}
                    layout=${`${selectedKey ?? ''}:${selected?.items.length ?? 0}:${shown === 0}:${folds}`} />
    </div>

    ${modalEntry !== undefined && html`
      <${ItemModal} trip=${store.trip} labels=${store.labels || []} entry=${modalEntry}
                    onClose=${() => setModalEntry(undefined)} />`}
  `;
}
