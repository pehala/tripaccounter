// The last time zone picked for an entry in each trip: a per-viewer convenience, so a
// trip crossing zones does not make every new entry start from the trip's own zone.
const key = (slug) => `ta.entryZone.${slug}`;

export function lastZone(trip) {
  try {
    return localStorage.getItem(key(trip.slug)) || trip.timezone;
  } catch {
    return trip.timezone;
  }
}

export function rememberZone(trip, zone) {
  try {
    localStorage.setItem(key(trip.slug), zone);
  } catch {
    // Storage blocked: the next entry starts from the trip's zone.
  }
}

// The time fields of a write. Changing only the zone of a row keeps its instant;
// typing the time as well means the typed time was right, so both go.
export function whenBody(state, original, toInput, fromInput) {
  const occurredAt = fromInput(state.occurredAt);
  if (original && state.occurredTz !== original.occurred_tz
      && state.occurredAt === toInput(original.occurred_at)) {
    return { occurred_tz: state.occurredTz };
  }
  return { occurred_at: occurredAt, occurred_tz: state.occurredTz };
}
