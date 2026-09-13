import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, load } from '../store.js';
import { t, LANGS, getLocale, setLocale } from '../i18n/index.js';
import { dateRange } from '../fmt.js';
import { Items } from './Items.js';
import { Balances } from './Balances.js';
import { Stats } from './Stats.js';
import { Setup } from './Setup.js';
import { Flash } from '../components/Flash.js';

const TABS = [
  ['items', 'nav.items'],
  ['balances', 'nav.balances'],
  ['stats', 'nav.stats'],
  ['setup', 'nav.setup'],
];

function currentTheme() {
  return document.documentElement.dataset.bsTheme === 'dark' ? 'dark' : 'light';
}

if (localStorage.getItem('theme')) {
  document.documentElement.dataset.bsTheme = localStorage.getItem('theme');
}

export function Trip({ slug, tab }) {
  const store = useStore();
  const [theme, setTheme] = useState(currentTheme());

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.bsTheme = next;
    localStorage.setItem('theme', next);
    setTheme(next);
  }

  useEffect(() => {
    if (store.slug !== slug) load(slug);
  }, [slug]);

  if (store.slug !== slug || !store.trip) {
    if (store.error?.status === 404) {
      return html`<div class="container py-4">
        <h1 class="h4">${t('notfound.title')}</h1>
        <p class="text-body-secondary">${t('notfound.body')}</p>
      </div>`;
    }
    if (store.error) return html`<div class="container py-4"><p class="text-danger">${t('app.error')}</p></div>`;
    return html`<div class="container py-4">${t('app.loading')}</div>`;
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
    <header class="bg-body border-bottom sticky-top">
      <div class="container" style="max-width:48rem">
        <div class="d-flex align-items-baseline gap-2 flex-wrap pt-3">
          <h1 class="h5 mb-0">${trip.name}</h1>
          <small class="text-body-secondary">${subtitle}</small>
          <div class="dropdown ms-auto">
            <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="dropdown" aria-expanded="false">⋯</button>
            <ul class="dropdown-menu dropdown-menu-end">
              <li><h6 class="dropdown-header">${t('lang.menu')}</h6></li>
              ${Object.keys(LANGS).map((lang) => html`
                <li key=${lang}>
                  <button class="dropdown-item ${lang === locale ? 'active' : ''}" type="button"
                          onClick=${() => setLocale(lang)}>${t(`lang.${lang}`)}</button>
                </li>
              `)}
              <li><hr class="dropdown-divider" /></li>
              <li>
                <button class="dropdown-item" type="button" onClick=${toggleTheme}>
                  <i class="bi ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}"></i>
                  ${theme === 'dark' ? t('theme.light') : t('theme.dark')}
                </button>
              </li>
            </ul>
          </div>
        </div>
        <ul class="nav nav-tabs border-0 mt-2" role="tablist">
          ${TABS.map(([key, labelKey]) => html`
            <li key=${key} class="nav-item">
              <a class="nav-link ${key === tab ? 'active' : ''}" href="/t/${slug}#${key}">${t(labelKey)}</a>
            </li>
          `)}
        </ul>
      </div>
    </header>

    <main class="container py-3" style="max-width:48rem">
      ${tab === 'items' && html`<${Items} />`}
      ${tab === 'balances' && html`<${Balances} />`}
      ${tab === 'stats' && html`<${Stats} />`}
      ${tab === 'setup' && html`<${Setup} />`}
    </main>
  `;
}
