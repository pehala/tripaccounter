// The one needle matcher, shared by the item feed and the map, so the two tabs
// always agree on what "filter by name or label" reaches.
export function itemMatches(item, needle) {
  return item.name.toLowerCase().includes(needle) || item.labels.some((name) => name.includes(needle));
}

// The stay search: its own text, or any expense grouped under it.
export function stayMatches(stay, country, items, needle) {
  const text = [stay.name, stay.city, stay.note, country?.name].filter(Boolean).join(' ').toLowerCase();
  return text.includes(needle) || items.some((item) => itemMatches(item, needle));
}
