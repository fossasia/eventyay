const DEFAULT_TILES = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png";
const DEFAULT_ATTRIB =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const DEFAULT_ZOOM = 15;

const maps = [];

function initMap(grp) {
  const latStr = grp.dataset.lat;
  const lonStr = grp.dataset.lon;

  if (!latStr || !lonStr) return;

  const lat = parseFloat(latStr.replace(",", "."));
  const lon = parseFloat(lonStr.replace(",", "."));

  if (isNaN(lat) || isNaN(lon)) return;

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
  document.querySelectorAll(".public-geodata-group").forEach(initMap);
}

window.addEventListener("resize", () => {
  maps.forEach((m) => m.invalidateSize());
});

document.addEventListener("DOMContentLoaded", initGeoMaps);
