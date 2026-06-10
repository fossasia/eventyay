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

  const map = L.map(target).setView([lat, lon], DEFAULT_ZOOM);

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
