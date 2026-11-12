/**
 * "Restrict access to tracks" in the team permissions form.
 *
 * Mirrors the "Limit to events" pattern: an "All tracks" checkbox and, when it
 * is unchecked, one list of tracks grouped by event with All / None helpers.
 * Only events the team can access are shown, and the form cannot be submitted
 * with track limits switched on but no track selected.
 *
 * Expected DOM structure (per form):
 *   input#<all tracks id>
 *   .team-track-limits[data-all-tracks-id][data-all-events-id][data-limit-events-name]
 *     .team-track-empty-warning
 *     [data-track-select="all|none"]            (whole list)
 *     .team-track-group[data-event-id]
 *       [data-selection-count]
 *       [data-track-select="all|none"]          (this event only)
 *       input[type="checkbox"]
 *     .team-track-out-of-scope
 */

function trackBoxes(group) {
    return Array.from(group.querySelectorAll('input[type="checkbox"]'));
}

function updateCount(group) {
    const countEl = group.querySelector('[data-selection-count]');
    if (!countEl) {
        return;
    }
    const boxes = trackBoxes(group);
    const selected = boxes.filter(function (box) {
        return box.checked;
    }).length;
    countEl.textContent = `${selected} / ${boxes.length}`;
}

function initTrackLimits(container) {
    if (container.dataset.initialized) {
        return;
    }
    container.dataset.initialized = 'true';

    const form = container.closest('form');
    const scope = form || document;
    const allTracks = document.getElementById(container.dataset.allTracksId);
    const allEvents = document.getElementById(container.dataset.allEventsId);
    const eventBoxes = Array.from(
        scope.querySelectorAll(`input[name="${CSS.escape(container.dataset.limitEventsName || '')}"]`)
    );
    const groups = Array.from(container.querySelectorAll('.team-track-group'));
    const outOfScope = container.querySelector('.team-track-out-of-scope');
    const warning = container.querySelector('.team-track-empty-warning');

    function visibleGroups() {
        return groups.filter(function (group) {
            return !group.hidden;
        });
    }

    function accessibleEventIds() {
        if (!allEvents || allEvents.checked) {
            return null;
        }
        return new Set(
            eventBoxes
                .filter(function (box) {
                    return box.checked;
                })
                .map(function (box) {
                    return box.value;
                })
        );
    }

    function refresh() {
        container.hidden = Boolean(allTracks && allTracks.checked);
        const eventIds = accessibleEventIds();
        groups.forEach(function (group) {
            group.hidden = eventIds !== null && !eventIds.has(group.dataset.eventId);
            updateCount(group);
        });
        if (outOfScope) {
            outOfScope.hidden = visibleGroups().length > 0;
        }
        if (warning) {
            warning.hidden = true;
        }
    }

    container.addEventListener('click', function (event) {
        const link = event.target.closest('[data-track-select]');
        if (!link || !container.contains(link)) {
            return;
        }
        event.preventDefault();
        const ownGroup = link.closest('.team-track-group');
        const targets = ownGroup ? [ownGroup] : visibleGroups();
        const checked = link.dataset.trackSelect === 'all';
        targets.forEach(function (group) {
            trackBoxes(group).forEach(function (box) {
                box.checked = checked;
            });
            updateCount(group);
        });
    });

    container.addEventListener('change', function (event) {
        const group = event.target.closest('.team-track-group');
        if (group) {
            updateCount(group);
        }
        if (warning) {
            warning.hidden = true;
        }
    });

    [allTracks, allEvents].concat(eventBoxes).forEach(function (input) {
        if (input) {
            input.addEventListener('change', refresh);
        }
    });

    if (form) {
        form.addEventListener('submit', function (event) {
            const restricting = allTracks && !allTracks.checked && container.offsetParent !== null;
            if (!restricting) {
                return;
            }
            const anySelected = visibleGroups().some(function (group) {
                return trackBoxes(group).some(function (box) {
                    return box.checked;
                });
            });
            if (!anySelected && visibleGroups().length > 0) {
                event.preventDefault();
                if (warning) {
                    warning.hidden = false;
                    warning.scrollIntoView({ block: 'center' });
                }
            }
        });
    }

    refresh();
}

function initAllTrackLimits(root = document) {
    root.querySelectorAll('.team-track-limits').forEach(initTrackLimits);
}

initAllTrackLimits();

document.addEventListener('DOMContentLoaded', function () {
    initAllTrackLimits();
});

export { initAllTrackLimits };
