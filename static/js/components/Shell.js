import { useEffect, useRef, useState } from 'preact/hooks';
import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { api } from '../api.js';
import { ThemeLangMenu } from './ThemeLangMenu.js';

// Trips come back newest-first (backend orders by created_at desc), so the
// first 5 are the most recently created — cheap to reuse as "recent". Fetched
// lazily, on the dropdown's own open event, so every other page load stays
// on its own call budget instead of always paying for a list it may not open.
function useRecentTrips() {
  const [trips, setTrips] = useState(null);
  const toggleRef = useRef(null);

  useEffect(() => {
    const toggle = toggleRef.current;
    if (!toggle) return;
    function onShow() {
      if (trips !== null) return;
      api.get('/trips').then((r) => setTrips(r.trips.slice(0, 5))).catch(() => setTrips([]));
    }
    toggle.addEventListener('show.bs.dropdown', onShow);
    return () => toggle.removeEventListener('show.bs.dropdown', onShow);
  }, [trips]);

  return [trips || [], toggleRef];
}

// `children` is everything route-specific (trip list, new-trip form, a
// trip's own header and tabs), drawn by app.js underneath this nav.
export function Shell({ children }) {
  const [recentTrips, toggleRef] = useRecentTrips();

  return html`
    <nav class="navbar navbar-expand bg-body border-bottom shell-bar py-1 small">
      <div class="container" style="max-width:48rem">
        <!-- alt="" keeps the mark decorative: the brand text beside it already names the link. -->
        <a class="navbar-brand fw-semibold fs-6 me-3" href="/">
          <img src="/favicon.svg" alt="" width="18" height="18" class="d-inline-block align-text-bottom me-1" />
          ${t('app.name')}</a>
        <ul class="navbar-nav me-auto">
          <li class="nav-item dropdown">
            <a ref=${toggleRef} class="nav-link py-1 dropdown-toggle" href="/" data-bs-toggle="dropdown" aria-expanded="false">${t('trips.title')}</a>
            <ul class="dropdown-menu small">
              ${recentTrips.map((trip) => html`
                <li key=${trip.id}><a class="dropdown-item py-1" href="/t/${trip.slug}">${trip.name}</a></li>
              `)}
              ${recentTrips.length > 0 && html`<li><hr class="dropdown-divider" /></li>`}
              <li><a class="dropdown-item py-1" href="/">${t('trips.all')}</a></li>
            </ul>
          </li>
          <li class="nav-item"><a class="nav-link py-1" href="/trips/new">${t('trips.new')}</a></li>
        </ul>
        <${ThemeLangMenu} />
      </div>
    </nav>
    ${children}
  `;
}
