/**
 * Venue Map Initialization
 * Initializes Leaflet map for venue location display
 */
(function() {
    'use strict';
    
    function initVenueMap() {
        var mapContainer = document.getElementById('venue-map');
        if (!mapContainer) {
            return;
        }
        
        var lat = parseFloat(mapContainer.dataset.lat);
        var lon = parseFloat(mapContainer.dataset.lon);
        var location = mapContainer.dataset.location;
        var errorMessage = mapContainer.dataset.errorMessage;
        
        // Validate coordinates
        if (isNaN(lat) || isNaN(lon)) {
            console.error('Invalid coordinates');
            return;
        }
        
        // Check if Leaflet is available
        if (typeof L === 'undefined') {
            mapContainer.innerHTML = '<p class="venue-map-error">' + errorMessage + '</p>';
            console.error('Leaflet library is not available');
            return;
        }
        
        try {
            // Fix Leaflet's default icon paths
            delete L.Icon.Default.prototype._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
                iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
                shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
            });
            
            // Initialize map
            var map = L.map('venue-map').setView([lat, lon], 15);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 18,
            }).addTo(map);
            
            // Add marker
            var marker = L.marker([lat, lon]).addTo(map);
            
            // Add popup if location text is provided
            if (location) {
                marker.bindPopup(location);
            }
        } catch (e) {
            mapContainer.innerHTML = '<p class="venue-map-error">' + errorMessage + '</p>';
            console.error('Error during Leaflet map initialization:', e);
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVenueMap);
    } else {
        initVenueMap();
    }
})();
