import { useEffect, useState } from 'preact/hooks';
import { api } from './api.js';

// Per-trip state: trip, labels, items, balances, stats. Plain object + subscribers,
// so any component can read it with useStore() and re-render when it changes.
const state = {
  slug: null,
  trip: null,
  labels: null,
  items: null,
  balances: null,
  stats: null,
  error: null,
};

const listeners = new Set();
function notify() { listeners.forEach((fn) => fn()); }

export function useStore() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((n) => n + 1);
    listeners.add(fn);
    return () => listeners.delete(fn);
  }, []);
  return state;
}

const LOADERS = {
  trip: (slug) => api.get(`/trips/${slug}`).then((r) => { state.trip = r.trip; }),
  labels: (slug) => api.get(`/trips/${slug}/labels`).then((r) => { state.labels = r.labels; }),
  items: (slug) => api.get(`/trips/${slug}/items`).then((r) => { state.items = r.items; }),
  balances: (slug) => api.get(`/trips/${slug}/balances`).then((r) => { state.balances = r.balances; }),
  stats: (slug) => api.get(`/trips/${slug}/stats`).then((r) => { state.stats = r.stats; }),
};

export async function reload(kind) {
  await LOADERS[kind](state.slug);
  notify();
}

export async function load(slug) {
  state.slug = slug;
  state.trip = state.labels = state.items = state.balances = state.stats = null;
  state.error = null;
  notify();
  try {
    await Promise.all([reload('trip'), reload('items'), reload('labels')]);
  } catch (err) {
    state.error = err;
    notify();
  }
}
