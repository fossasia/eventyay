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

    const handlePossibleOutsideInteraction = function(event) {
        getOpenDropdowns().forEach(function(dropdown) {
            if (!dropdown.contains(event.target)) {
                dropdown.open = false;
            }
        });
    };
    document.addEventListener('pointerdown', handlePossibleOutsideInteraction, true);

    document.addEventListener('keydown', function(event) {
        if (event.key !== 'Escape' && event.key !== 'Esc') return;
        closeAllDropdowns();
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

    // Initialize dashboard dropdown submenu toggle for touch/keyboard devices
    document.querySelectorAll('.dashboard-dropdown-toggle').forEach(function(toggle) {
        toggle.addEventListener('click', function(event) {
            // Only prevent default and toggle on non-hover devices
            // Check if this is a touch device or doesn't support hover
            const supportsHover = window.matchMedia('(hover: hover)').matches;
            if (!supportsHover) {
                event.preventDefault();
                const parent = toggle.closest('.dashboard-dropdown');
                if (parent) {
                    parent.classList.toggle('active');
                    const isExpanded = parent.classList.contains('active');
                    toggle.setAttribute('aria-expanded', isExpanded.toString());
                }
            }
        });

        // Keyboard support (Enter and Space keys)
        toggle.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                const parent = toggle.closest('.dashboard-dropdown');
                if (parent) {
                    parent.classList.toggle('active');
                    const isExpanded = parent.classList.contains('active');
                    toggle.setAttribute('aria-expanded', isExpanded.toString());
                }
            }
        });
    });

    // Close submenu when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.dashboard-dropdown')) {
            document.querySelectorAll('.dashboard-dropdown.active').forEach(function(dropdown) {
                dropdown.classList.remove('active');
                const toggle = dropdown.querySelector('.dashboard-dropdown-toggle');
                if (toggle) {
                    toggle.setAttribute('aria-expanded', 'false');
                }
            });
        }
    });
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDropdowns);
} else {
    initDropdowns();
}

export { initDropdowns };
