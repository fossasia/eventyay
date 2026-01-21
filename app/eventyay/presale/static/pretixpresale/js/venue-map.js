/**
 * Venue Map Initialization
 * Initializes Leaflet map for venue location display
 */
(function() {
    'use strict';
    
    function showError(container, message) {
        // Safely create error message element to avoid XSS
        var errorElement = document.createElement('p');
        errorElement.className = 'venue-map-error';
        errorElement.textContent = message;
        container.innerHTML = ''; // Clear container first
        container.appendChild(errorElement);
    }
    
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
            showError(mapContainer, errorMessage);
            console.error('Leaflet library is not available');
            return;
        }
        
        try {
            // Fix Leaflet's default icon paths
            delete L.Icon.Default.prototype._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: mapContainer.dataset.iconRetinaUrl,
                iconUrl: mapContainer.dataset.iconUrl,
                shadowUrl: mapContainer.dataset.shadowUrl,
            });
            
            // Initialize map with zoom control on right side
            var map = L.map('venue-map', {
                zoomControl: false  // Disable default zoom control
            }).setView([lat, lon], 15);
            
            // Add zoom control to top-right to avoid overlaying form elements
            L.control.zoom({
                position: 'topright'
            }).addTo(map);
            
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
            showError(mapContainer, errorMessage);
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
