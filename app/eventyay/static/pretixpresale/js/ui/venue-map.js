/**
 * Initialize venue map on public event page
 */
(function() {
    'use strict';

    function initVenueMap() {
        var mapElement = document.getElementById('venue-map');
        if (!mapElement) {
            return;
        }

        var lat = parseFloat(mapElement.dataset.lat);
        var lon = parseFloat(mapElement.dataset.lon);
        var location = mapElement.dataset.location || '';

        if (isNaN(lat) || isNaN(lon)) {
            console.error('Invalid coordinates for venue map');
            return;
        }

        var map = L.map('venue-map').setView([lat, lon], 15);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 18,
        }).addTo(map);

        var marker = L.marker([lat, lon]).addTo(map);
        
        if (location) {
            marker.bindPopup(location);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVenueMap);
    } else {
        initVenueMap();
    }
})();
