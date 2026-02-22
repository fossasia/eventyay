/**
 * Event-track selector for Team permissions.
 *
 * Provides interactive filtering of tracks by event using a dropdown,
 * with "All" / "None" quick-select helpers per event group.
 *
 * Expected DOM structure (per selector):
 *   .event-track-selector
 *     select.event-track-filter
 *     .event-tracks-placeholder
 *     .event-track-group[data-event-group-id]
 *       .track-select-all[data-event-id]
 *       .track-select-none[data-event-id]
 */
(function () {
    'use strict';

    function initEventTrackSelectors() {
        document.querySelectorAll('.event-track-filter').forEach(function (select) {
            if (select.dataset.initialized) return;
            select.dataset.initialized = 'true';

            var container = select.closest('.event-track-selector');
            if (!container) return;

            select.addEventListener('change', function () {
                var selectedEventId = this.value;
                var placeholder = container.querySelector('.event-tracks-placeholder');
                var groups = container.querySelectorAll('.event-track-group');

                groups.forEach(function (group) {
                    group.style.display = 'none';
                });

                if (selectedEventId) {
                    if (placeholder) placeholder.style.display = 'none';
                    var targetGroup = container.querySelector(
                        '[data-event-group-id="' + selectedEventId + '"]'
                    );
                    if (targetGroup) {
                        targetGroup.style.display = 'block';
                    }
                } else {
                    if (placeholder) placeholder.style.display = 'block';
                }
            });

            container.querySelectorAll('.track-select-all').forEach(function (link) {
                link.addEventListener('click', function (e) {
                    e.preventDefault();
                    var eventId = this.getAttribute('data-event-id');
                    var group = container.querySelector(
                        '[data-event-group-id="' + eventId + '"]'
                    );
                    if (group) {
                        group.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
                            cb.checked = true;
                        });
                    }
                });
            });

            container.querySelectorAll('.track-select-none').forEach(function (link) {
                link.addEventListener('click', function (e) {
                    e.preventDefault();
                    var eventId = this.getAttribute('data-event-id');
                    var group = container.querySelector(
                        '[data-event-group-id="' + eventId + '"]'
                    );
                    if (group) {
                        group.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
                            cb.checked = false;
                        });
                    }
                });
            });

            // Auto-select when there is only one event
            if (select.options.length === 2) {
                select.selectedIndex = 1;
                select.dispatchEvent(new Event('change'));
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEventTrackSelectors);
    } else {
        initEventTrackSelectors();
    }

    // Re-initialise when Bootstrap collapse panels are shown
    // (team permission panels may be initially collapsed).
    if (typeof $ !== 'undefined') {
        $(document).on('shown.bs.collapse', function () {
            initEventTrackSelectors();
        });
    }
})();
