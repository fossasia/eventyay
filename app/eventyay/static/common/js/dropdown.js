(function() {
    'use strict';

    // Behavior:
    // - Close dropdowns on outside click
    // - Close dropdowns on Escape
    // - When a dropdown opens, close other open dropdowns (except ancestors/descendants)

    const GLOBAL_INIT_FLAG = 'eventyayDropdownGlobalInit';
    const initializedDropdowns = new WeakSet();

    const getOpenDropdowns = function() {
        return document.querySelectorAll('details.dropdown[open]');
    };

    const closeAllDropdowns = function() {
        getOpenDropdowns().forEach(function(dropdown) {
            dropdown.open = false;
        });
    };

    const closeOtherDropdowns = function(current) {
        getOpenDropdowns().forEach(function(other) {
            if (other === current) return;
            // Keep ancestors and descendants open to support nested dropdowns.
            if (other.contains(current)) return;
            if (current.contains(other)) return;
            other.open = false;
        });
    };

    const ensureGlobalListeners = function() {
        if (document.documentElement.dataset[GLOBAL_INIT_FLAG] === '1') {
            return;
        }
        document.documentElement.dataset[GLOBAL_INIT_FLAG] = '1';

        document.addEventListener('click', function(event) {
            getOpenDropdowns().forEach(function(dropdown) {
                if (!dropdown.contains(event.target)) {
                    dropdown.open = false;
                }
            });
        });

        document.addEventListener('keydown', function(event) {
            if (event.key !== 'Escape' && event.key !== 'Esc') return;
            closeAllDropdowns();
        });

        // Special handling for language selector to prevent form submission interference
        document.addEventListener('click', function(event) {
            const languageDropdown = event.target.closest('.language-switch details.dropdown');
            if (languageDropdown) {
                // Allow clicks on dropdown items to work normally
                const dropdownItem = event.target.closest('.dropdown-item');
                if (!dropdownItem) {
                    // If clicking outside the dropdown content, close it
                    if (!languageDropdown.contains(event.target)) {
                        languageDropdown.open = false;
                    }
                }
            }
        });
    };

    const initDropdowns = function() {
        ensureGlobalListeners();

        document.querySelectorAll('details.dropdown').forEach(function(dropdown) {
            if (initializedDropdowns.has(dropdown)) return;
            initializedDropdowns.add(dropdown);

            dropdown.addEventListener('toggle', function() {
                if (!dropdown.open) return;
                closeOtherDropdowns(dropdown);
            });
        });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDropdowns);
    } else {
        initDropdowns();
    }
})();
