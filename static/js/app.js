import { h, render } from './h.js';
import { onLocaleChange, t } from './i18n/index.js';
import { TripList } from './views/TripList.js';
import { TripNew } from './views/TripNew.js';
import { Trip } from './views/Trip.js';
import { Shell } from './components/Shell.js';

const root = document.getElementById('app');

function parseRoute() {
  const path = location.pathname;
  const m = path.match(/^\/t\/([^/]+)(?:\/([^/]+))?\/?$/);
  if (m) return { name: 'trip', slug: m[1], tab: m[2] || 'items' };
  if (path === '/trips/new') return { name: 'trip-new' };
  return { name: 'trips' };
}

function draw() {
  const route = parseRoute();
  document.title = t('app.name');
  const view = route.name === 'trip'
    ? h(Trip, { slug: route.slug, tab: route.tab })
    : route.name === 'trip-new'
      ? h(TripNew, {})
      : h(TripList, {});
  render(h(Shell, null, view), root);
}

// Intercept same-origin link clicks so tab/trip navigation never reloads the page.
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="/"]');
  if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  if (a.getAttribute('href') !== location.pathname) {
    history.pushState(null, '', a.getAttribute('href'));
  }
  draw();
});

window.addEventListener('popstate', draw);
onLocaleChange(draw);

draw();
