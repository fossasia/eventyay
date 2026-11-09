const DEFAULT_TILES = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png";
const DEFAULT_ATTRIB =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const DEFAULT_ZOOM = 15;
const NULL_ISLAND_EPSILON = 1e-6;

const maps = [];
let hoveredMap = null;

/**
 * Parse coordinate string to floating-point number.
 * @param {*} value - Coordinate value or string.
 * @returns {number|null} Parsed number or null if invalid.
 */
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

/**
 * Validate latitude and longitude coordinate pair.
 * @param {number|null} lat - Latitude.
 * @param {number|null} lon - Longitude.
 * @returns {boolean} True if coordinates are valid and not null island.
 */
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

/**
 * Check if keyboard event corresponds to a zoom-in key.
 * @param {KeyboardEvent} e - Keyboard event.
 * @returns {boolean} True if key represents zoom-in.
 */
const isZoomInKey = (e) =>
  e.key === "+" ||
  e.key === "=" ||
  e.key === "Add" ||
  e.code === "Equal" ||
  e.code === "NumpadAdd";

/**
 * Check if keyboard event corresponds to a zoom-out key.
 * @param {KeyboardEvent} e - Keyboard event.
 * @returns {boolean} True if key represents zoom-out.
 */
const isZoomOutKey = (e) =>
  e.key === "-" ||
  e.key === "_" ||
  e.key === "Subtract" ||
  e.code === "Minus" ||
  e.code === "NumpadSubtract";

window.addEventListener("blur", () => {
  hoveredMap = null;
});

window.addEventListener("focus", () => {
  const hoveredEl =
    typeof document.querySelector === "function"
      ? document.querySelector(".public-geodata-group:hover")
      : null;
  if (hoveredEl && hoveredEl._leaflet_map) {
    hoveredMap = hoveredEl._leaflet_map;
  }
});

window.addEventListener("keydown", (e) => {
  const target = e.target;
  if (
    target instanceof Element &&
    (target.isContentEditable ||
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT")
  ) {
    return;
  }

  if (!hoveredMap) {
    const hoveredEl =
      typeof document.querySelector === "function"
        ? document.querySelector(".public-geodata-group:hover")
        : null;
    if (hoveredEl && hoveredEl._leaflet_map) {
      hoveredMap = hoveredEl._leaflet_map;
    }
  }
  if (!hoveredMap) return;
  if (e.ctrlKey || e.metaKey) {
    let zoomAction = null;
    if (isZoomInKey(e)) {
      zoomAction = () => hoveredMap.zoomIn();
    } else if (isZoomOutKey(e)) {
      zoomAction = () => hoveredMap.zoomOut();
    } else if (e.key === "0" || e.code === "Digit0" || e.code === "Numpad0") {
      zoomAction = () => hoveredMap.setZoom(DEFAULT_ZOOM);
    }

    if (zoomAction) {
      e.preventDefault();
      if (typeof hoveredMap._cancelPendingZoom === "function") {
        hoveredMap._cancelPendingZoom();
      }
      zoomAction();
    }
  }
});

/**
 * Initialize a Leaflet map inside a geodata group container.
 * @param {HTMLElement} grp - Geodata group DOM element.
 */
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
    zoomSnap: 0,
  }).setView([lat, lon], DEFAULT_ZOOM);

  grp._leaflet_map = map;

  grp.addEventListener("mouseenter", () => {
    hoveredMap = map;
  });
  grp.addEventListener("mouseleave", () => {
    if (hoveredMap === map) hoveredMap = null;
  });

  let pendingZoom = null;
  let pendingPoint = null;
  let rafId = null;
  let isInternalZoom = false;

  function cancelPendingZoom() {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    pendingZoom = null;
    pendingPoint = null;
  }

  map._cancelPendingZoom = cancelPendingZoom;

  map.on("zoomstart", () => {
    if (!isInternalZoom) {
      cancelPendingZoom();
    }
  });

  function applyZoom() {
    if (pendingZoom !== null && pendingPoint !== null) {
      const targetZ = pendingZoom;
      const targetP = pendingPoint;
      cancelPendingZoom();
      isInternalZoom = true;
      try {
        map.setZoomAround(targetP, targetZ);
      } finally {
        isInternalZoom = false;
      }
    }
  }

  grp.addEventListener(
    "wheel",
    (e) => {
      if (!e.ctrlKey && !e.metaKey) {
        return;
      }
      e.preventDefault();
      const zoomPoint = map.mouseEventToContainerPoint(e);
      const deltaPixels =
        e.deltaMode === 1 ? e.deltaY * 33 : e.deltaMode === 2 ? e.deltaY * 100 : e.deltaY;
      const step = Math.max(-1, Math.min(1, -deltaPixels / 100));
      if (step !== 0) {
        pendingPoint = zoomPoint;
        const currentZoom = pendingZoom !== null ? pendingZoom : map.getZoom();
        pendingZoom = Math.max(
          map.getMinZoom(),
          Math.min(map.getMaxZoom(), currentZoom + step)
        );
        if (!rafId) {
          rafId = requestAnimationFrame(applyZoom);
        }
      }
    },
    { passive: false }
  );

  let gestureBaseZoom = null;
  let isTouchPinch = false;

  grp.addEventListener("touchstart", (e) => {
    if (e.touches && e.touches.length > 1) {
      isTouchPinch = true;
    }
  }, { passive: true });
  grp.addEventListener("touchend", () => {
    isTouchPinch = false;
  }, { passive: true });
  grp.addEventListener("touchcancel", () => {
    isTouchPinch = false;
  }, { passive: true });

  grp.addEventListener("gesturestart", (e) => {
    e.preventDefault();
    gestureBaseZoom = map.getZoom();
  });
  grp.addEventListener("gesturechange", (e) => {
    e.preventDefault();
    if (isTouchPinch) {
      // Allow Leaflet's built-in touchZoom handler to manage touch pinch
      return;
    }
    if (gestureBaseZoom === null) {
      gestureBaseZoom = map.getZoom();
    }
    pendingZoom = Math.max(
      map.getMinZoom(),
      Math.min(map.getMaxZoom(), gestureBaseZoom + Math.log2(e.scale))
    );
    pendingPoint =
      typeof e.clientX === "number"
        ? map.mouseEventToContainerPoint(e)
        : map.getSize().divideBy(2);
    if (!rafId) {
      rafId = requestAnimationFrame(applyZoom);
    }
  });
  grp.addEventListener("gestureend", (e) => {
    e.preventDefault();
    if (rafId) {
      cancelAnimationFrame(rafId);
      applyZoom();
    }
    gestureBaseZoom = null;
    isTouchPinch = false;
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
