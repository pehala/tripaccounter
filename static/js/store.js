import { useEffect, useState } from 'preact/hooks';
import { api } from './api.js';

// Per-trip state: trip, labels, items, transfers, balances, wallets, stats. Plain
// object + subscribers, so any component can read it with useStore() and re-render
// when it changes.
const state = {
  slug: null,
  trip: null,
  labels: null,
  items: null,
  dayTotals: null,
  beforeTripTotals: null,
  transfers: null,
  balances: null,
  wallets: null,
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
  items: (slug) => api.get(`/trips/${slug}/items`).then((r) => {
    state.items = r.items;
    state.dayTotals = r.day_totals;
    state.beforeTripTotals = r.before_trip_totals;
    state.transfers = r.transfers;
  }),
  balances: (slug) => api.get(`/trips/${slug}/balances`).then((r) => { state.balances = r.balances; }),
  wallets: (slug) => api.get(`/trips/${slug}/wallets`).then((r) => { state.wallets = r.wallets; }),
  stats: (slug) => api.get(`/trips/${slug}/stats`).then((r) => { state.stats = r.stats; }),
};

export async function reload(kind) {
  await LOADERS[kind](state.slug);
  notify();
}

// A write that can change money movement (an item or a transfer) invalidates the
// two tabs that summarize it, so the next visit refetches instead of showing a
// stale figure - the same store.x ? skip : reload(x) pattern Balances/Wallets use.
export function invalidateMoneyViews() {
  state.wallets = null;
  state.balances = null;
  notify();
}

export async function load(slug) {
  state.slug = slug;
  state.trip = state.labels = state.items = state.dayTotals = state.beforeTripTotals = null;
  state.transfers = state.balances = state.wallets = state.stats = null;
  state.error = null;
  notify();
  try {
    await reload('trip');
  } catch (err) {
    state.error = err;
    notify();
  }
}
