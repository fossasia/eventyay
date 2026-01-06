(function() {
    'use strict';
    
    var initDropdowns = function() {
        var dropdowns = document.querySelectorAll('details.dropdown');

        dropdowns.forEach(function(dropdown) {
            dropdown.addEventListener('toggle', function() {
                if (!dropdown.open) {
                    return;
                }
                dropdowns.forEach(function(other) {
                    if (other !== dropdown && other.open && !other.contains(dropdown)) {
                        other.open = false;
                    }
                });
            });
        });

        document.addEventListener('click', function(event) {
            dropdowns.forEach(function(dropdown) {
                if (dropdown.open && !dropdown.contains(event.target)) {
                    dropdown.open = false;
                }
            });
        });

        document.addEventListener('keydown', function(event) {
            if (event.key !== 'Escape' && event.key !== 'Esc') {
                return;
            }
            dropdowns.forEach(function(dropdown) {
                dropdown.open = false;
            });
        });
    };
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDropdowns);
    } else {
        initDropdowns();
    }
})();
