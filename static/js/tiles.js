// The basemap the map tab draws on. OpenStreetMap's standard raster tiles need no
// key; its tile usage policy (https://operations.osmfoundation.org/policies/tiles/)
// asks for visible credit and viewport-only fetching, which is what Leaflet does.
// The credit is a legal attribution, not UI wording, so it never goes through the
// catalog and is never translated.
export const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
export const TILE_MAX_ZOOM = 19;
export const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
