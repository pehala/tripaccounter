// The one needle matcher, shared by the item feed and the map, so the two tabs
// always agree on what "filter by name or label" reaches.
export function itemMatches(item, needle) {
  return item.name.toLowerCase().includes(needle) || item.labels.some((name) => name.includes(needle));
}
