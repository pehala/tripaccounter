import { useEffect, useRef, useState } from 'preact/hooks';
import { html } from '../h.js';
import { TILE_ATTRIBUTION, TILE_MAX_ZOOM, TILE_URL } from '../tiles.js';

// Leaflet owns every node inside the canvas div and Preact owns none of them, so the
// div renders empty once and the two never diff the same DOM. Leaflet itself is
// imported here, on mount, which keeps it off every other tab's critical path.

const PIN_RADIUS = 7;
const PIN_GROWTH = 2;
const PIN_MAX_EXTRA = 3;
const FIT_MAX_ZOOM = 15;
const STREET_ZOOM = 18;
const FIT_PADDING = 0.3;

export function MapCanvas({ points, selectedKey, focus, layout, onSelect }) {
  const nodeRef = useRef(null);
  const leafletRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const pinsRef = useRef([]);
  const selectRef = useRef(onSelect);
  const selectedRef = useRef(selectedKey);
  const [ready, setReady] = useState(false);
  selectRef.current = onSelect;
  selectedRef.current = selectedKey;

  useEffect(() => {
    let disposed = false;
    import('leaflet').then((leaflet) => {
      if (disposed) return;
      const instance = leaflet.map(nodeRef.current).setView([0, 0], 2);
      leaflet
        .tileLayer(TILE_URL, { maxZoom: TILE_MAX_ZOOM, attribution: TILE_ATTRIBUTION })
        .addTo(instance);
      instance.on('click', () => selectRef.current(null));
      leafletRef.current = leaflet;
      mapRef.current = instance;
      layerRef.current = leaflet.layerGroup().addTo(instance);
      setReady(true);
    });
    return () => {
      disposed = true;
      mapRef.current?.remove();
      leafletRef.current = mapRef.current = layerRef.current = null;
    };
  }, []);

  // CSS gives the canvas its size (app.css, .map-page); Leaflet follows a window
  // resize on its own, but not one the layout above it caused - `layout` is the view
  // saying it did.
  useEffect(() => {
    mapRef.current?.invalidateSize();
  }, [ready, layout]);

  // Rebuilt only when the point set changes: a marker replaced mid-gesture never sees
  // the second click, which is what a double-click is made of.
  useEffect(() => {
    const leaflet = leafletRef.current;
    if (!leaflet) return;
    layerRef.current.clearLayers();
    pinsRef.current = points.map((point) => {
      const extra = Math.min(point.items.length - 1, PIN_MAX_EXTRA);
      const pin = leaflet
        .circleMarker([point.lat, point.lon], {
          radius: PIN_RADIUS + extra * PIN_GROWTH,
          className: 'map-pin',
        })
        // Clicking the pin that is already selected is the zoom gesture: by then the
        // panel is open and nothing moves under the cursor, which is what makes a real
        // double-click unreliable here - the first click shifts the map down.
        .on('click', (event) => {
          leaflet.DomEvent.stop(event);
          if (selectedRef.current === point.key) {
            mapRef.current.setView([point.lat, point.lon], STREET_ZOOM);
            return;
          }
          selectRef.current(point.key);
        })
        .addTo(layerRef.current);
      pin.getElement().dataset.pin = point.key;
      return { key: point.key, pin };
    });
  }, [ready, points]);

  useEffect(() => {
    for (const { key, pin } of pinsRef.current) {
      pin.getElement()?.classList.toggle('map-pin-on', key === selectedKey);
    }
  }, [ready, points, selectedKey]);

  // The panel's own zoom button, for a pin the pointer is nowhere near.
  useEffect(() => {
    const point = focus && points.find((candidate) => candidate.key === focus.key);
    if (point) mapRef.current.setView([point.lat, point.lon], STREET_ZOOM);
  }, [ready, focus]);

  // Selecting a pin must not move the map under the finger that tapped it, so the
  // view is refitted when the visible set changes and never on selection alone.
  useEffect(() => {
    const leaflet = leafletRef.current;
    if (!leaflet || points.length === 0) return;
    const bounds = leaflet.latLngBounds(points.map((point) => [point.lat, point.lon]));
    mapRef.current.fitBounds(bounds.pad(FIT_PADDING), { maxZoom: FIT_MAX_ZOOM });
  }, [ready, points]);

  return html`<div class="map-canvas rounded shadow-sm flex-grow-1 z-0" ref=${nodeRef}></div>`;
}
