const DEFAULT_TILES = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png";
const DEFAULT_ATTRIB =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const DEFAULT_ZOOM = 15;
const NULL_ISLAND_EPSILON = 1e-6;

const maps = [];

function parseCoordinate(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const coordinate = Number.parseFloat(String(value).replace(",", "."));
  if (!Number.isFinite(coordinate)) {
    return null;
  }
  return coordinate;
}

function isValidCoordinatePair(lat, lon) {
  if (lat === null || lon === null) {
    return false;
  }
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    return false;
  }
  if (Math.abs(lat) < NULL_ISLAND_EPSILON && Math.abs(lon) < NULL_ISLAND_EPSILON) {
    return false;
  }
  return true;
}

function initMap(grp) {
  const lat = parseCoordinate(grp.dataset.lat);
  const lon = parseCoordinate(grp.dataset.lon);

  if (!isValidCoordinatePair(lat, lon)) return;

  const rawTiles = grp.dataset.tiles ?? "";
  const tiles = rawTiles.includes("{z}") ? rawTiles : DEFAULT_TILES;
  const attrib = grp.dataset.attrib || DEFAULT_ATTRIB;

  let target = grp.querySelector(".public-geodata-map");
  if (!target) {
    target = document.createElement("div");
    target.className = "public-geodata-map";
    grp.appendChild(target);
  }

  const map = L.map(target, {
    scrollWheelZoom: false,
  }).setView([lat, lon], DEFAULT_ZOOM);

  let accumulatedDelta = 0;
  let lastMousePos = null;
  let pinchDebounceTimer = null;

  function performPinchZoom() {
    if (Math.abs(accumulatedDelta) > 5) {
      const direction = accumulatedDelta < 0 ? 1 : -1;
      const currentZoom = map.getZoom();
      const newZoom = Math.max(
        map.getMinZoom(),
        Math.min(map.getMaxZoom(), currentZoom + direction)
      );
      if (newZoom !== currentZoom) {
        const centerPos = lastMousePos || map.getSize().divideBy(2);
        map.setZoomAround(centerPos, newZoom);
      }
    }
    accumulatedDelta = 0;
  }

  grp.addEventListener(
    "wheel",
    (e) => {
      if (!e.ctrlKey && !e.metaKey) {
        return;
      }

      e.preventDefault();
      lastMousePos = map.mouseEventToContainerPoint(e);
      accumulatedDelta += e.deltaY;

      const threshold = 60;
      if (Math.abs(accumulatedDelta) >= threshold) {
        clearTimeout(pinchDebounceTimer);
        performPinchZoom();
      } else {
        clearTimeout(pinchDebounceTimer);
        pinchDebounceTimer = setTimeout(performPinchZoom, 80);
      }
    },
    { passive: false }
  );

  grp.addEventListener("gesturestart", (e) => e.preventDefault());
  grp.addEventListener("gesturechange", (e) => e.preventDefault());
  grp.addEventListener("gestureend", (e) => e.preventDefault());

  let isHovered = false;
  grp.addEventListener("mouseenter", () => {
    isHovered = true;
  });
  grp.addEventListener("mouseleave", () => {
    isHovered = false;
  });
  grp.addEventListener("mousemove", () => {
    isHovered = true;
  });
  window.addEventListener("blur", () => {
    isHovered = false;
  });

  const isZoomInKey = (e) =>
    e.key === "+" ||
    e.key === "=" ||
    e.key === "Add" ||
    e.code === "Equal" ||
    e.code === "NumpadAdd";

  const isZoomOutKey = (e) =>
    e.key === "-" ||
    e.key === "_" ||
    e.key === "Subtract" ||
    e.code === "Minus" ||
    e.code === "NumpadSubtract";

  window.addEventListener("keydown", (e) => {
    if (!isHovered) return;
    if (e.ctrlKey || e.metaKey) {
      if (isZoomInKey(e)) {
        e.preventDefault();
        map.zoomIn();
      } else if (isZoomOutKey(e)) {
        e.preventDefault();
        map.zoomOut();
      } else if (e.key === "0" || e.code === "Digit0" || e.code === "Numpad0") {
        e.preventDefault();
        map.setZoom(DEFAULT_ZOOM);
      }
    }
  });

  L.tileLayer(tiles, {
    attribution: attrib,
    maxZoom: 18,
  }).addTo(map);

  const markerOptions = {};
  if (grp.dataset.icon) {
    markerOptions.icon = L.icon({
      iconUrl: grp.dataset.icon,
      shadowUrl: grp.dataset.shadow,
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      tooltipAnchor: [16, -28],
      shadowSize: [41, 41],
    });
  }

  L.marker([lat, lon], markerOptions).addTo(map);

  requestAnimationFrame(() => map.invalidateSize());
  maps.push(map);
}

function initGeoMaps() {
  if (typeof L === "undefined") {
    console.warn("Leaflet is not available, public venue maps were not initialized.");
    return;
  }
  document.querySelectorAll(".public-geodata-group").forEach(initMap);
}

window.addEventListener("resize", () => {
  maps.forEach((m) => m.invalidateSize());
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initGeoMaps);
} else {
  initGeoMaps();
}
