import { useEffect, useRef } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, load } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { dateRange } from '../fmt.js';
import { Items } from './Items.js';
import { Balances } from './Balances.js';
import { Wallets } from './Wallets.js';
import { Stats } from './Stats.js';
import { Map } from './Map.js';
import { Setup } from './Setup.js';
import { Flash } from '../components/Flash.js';
import { Loading } from '../components/Loading.js';

const TABS = [
  ['items', 'nav.items'],
  ['balances', 'nav.balances'],
  ['wallets', 'nav.wallets'],
  ['stats', 'nav.stats'],
  ['map', 'nav.map'],
  ['setup', 'nav.setup'],
];

export function Trip({ slug, tab }) {
  const store = useStore();
  const headerRef = useRef(null);

  useEffect(() => {
    if (store.slug !== slug) load(slug);
  }, [slug]);

  // The day separator sticks just below the header; the header's own height
  // varies with content (flags, currencies, locale), so track it instead of
  // guessing a fixed offset.
  useEffect(() => {
    if (!headerRef.current) return;
    const observer = new ResizeObserver(([entry]) => {
      document.documentElement.style.setProperty('--header-h', `${entry.target.offsetHeight}px`);
    });
    observer.observe(headerRef.current);
    return () => observer.disconnect();
  }, [store.trip]);

  if (store.slug !== slug || !store.trip) {
    if (store.error?.status === 404) {
      return html`<div class="container py-4">
        <h1 class="h4">${t('notfound.title')}</h1>
        <p class="text-body-secondary">${t('notfound.body')}</p>
      </div>`;
    }
    if (store.error) return html`<div class="container py-4"><p class="text-danger">${t('app.error')}</p></div>`;
    return html`<${Loading} />`;
  }

  const trip = store.trip;
  const locale = getLocale();
  const flags = trip.countries.map((c) => c.flag).filter(Boolean).join(' ');
  const currencyCodes = trip.currencies.map((c) => c.code).join(', ');
  const subtitle = [
    dateRange(trip.start_date, trip.end_date, locale),
    t('header.people', { n: trip.people.length }),
    flags,
    currencyCodes,
  ].join(' · ');

  return html`
    <${Flash} />
    <header class="bg-body border-bottom sticky-top" ref=${headerRef}>
      <div class="container">
        <div class="d-flex align-items-baseline gap-2 flex-wrap pt-3">
          <h1 class="h5 mb-0">${trip.name}</h1>
          <small class="text-body-secondary">${subtitle}</small>
        </div>
        <!-- Links doing real page loads, not ARIA tabs: aria-current marks the one
             we are on, which is what a screen reader wants from a nav. -->
        <nav class="mt-2" aria-label=${t('nav.sections')}>
          <ul class="nav nav-tabs border-0">
            ${TABS.map(([key, labelKey]) => html`
              <li key=${key} class="nav-item">
                <a class="nav-link ${key === tab ? 'active' : ''}"
                   aria-current=${key === tab ? 'page' : null}
                   href="/t/${slug}/${key}">${t(labelKey)}</a>
              </li>
            `)}
          </ul>
        </nav>
      </div>
    </header>

    <main class="container py-3">
      ${tab === 'items' && html`<${Items} />`}
      ${tab === 'balances' && html`<${Balances} />`}
      ${tab === 'wallets' && html`<${Wallets} />`}
      ${tab === 'stats' && html`<${Stats} />`}
      ${tab === 'map' && html`<${Map} />`}
      ${tab === 'setup' && html`<${Setup} />`}
    </main>
  `;
}
