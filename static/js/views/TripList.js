import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { api } from '../api.js';
import { t } from '../i18n/index.js';
import { Loading } from '../components/Loading.js';

export function TripList() {
  const [trips, setTrips] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get('/trips').then((r) => setTrips(r.trips)).catch(setError);
  }, []);

  return html`
    <div class="container py-4" style="max-width:48rem">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h4 mb-0">${t('trips.title')}</h1>
        <a href="/trips/new" class="btn btn-primary btn-sm">${t('trips.new')}</a>
      </div>
      ${error && html`<p class="text-danger">${t('app.error')}</p>`}
      ${!error && !trips && html`<${Loading} />`}
      ${!error && trips && html`
        ${trips.length === 0 && html`<p class="text-body-secondary">${t('trips.empty')}</p>`}
        <div class="list-group shadow-sm">
          ${trips.map((trip) => html`
            <a key=${trip.id} class="list-group-item list-group-item-action" href="/t/${trip.slug}">
              <span class="d-block fw-semibold">${trip.name}</span>
              <small class="text-body-secondary">${t('header.people', { n: trip.people_count })}</small>
            </a>
          `)}
        </div>
      `}
    </div>
  `;
}
