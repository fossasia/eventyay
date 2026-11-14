/**
 * "Limit to tracks" in the team permissions form.
 *
 * Works like "Limit to events": an "All tracks" checkbox and, when it is
 * unchecked, one scrollable checklist of tracks grouped by event. The list only
 * shows events the team can access (the "All events" / "Limit to events"
 * boxes above it), has All / None for the whole list and for each event, a
 * filter for long lists and a live summary. The server stays the authority: it
 * rejects an empty restriction and drops tracks of events outside the team.
 *
 * Expected DOM (per form):
 *   input#<all tracks id>
 *   .team-track-limits[data-all-tracks-id][data-all-events-id][data-limit-events-name]
 *     .team-track-empty-warning
 *     [data-track-summary]
 *     .team-track-search-row > input.team-track-search
 *     .team-track-list
 *       [data-track-select="all|none"]               (whole list)
 *       .team-track-group[data-event-id]
 *         [data-selection-count]
 *         [data-track-select="all|none"]             (this event only)
 *         .team-track-item[data-track-name] input[type="checkbox"]
 *       .team-track-search-empty
 *       .team-track-out-of-scope
 */

const FILTER_MIN_TRACKS = 8;

function trackBoxes(group) {
    return Array.from(group.querySelectorAll('.team-track-item input[type="checkbox"]'));
}

function countChecked(boxes) {
    return boxes.filter(function (box) {
        return box.checked;
    }).length;
}

function translate(singular, plural, count, values) {
    // Django's JavaScript catalog provides ngettext and interpolate; fall back to English without it.
    let template = count === 1 ? singular : plural;
    if (typeof window.ngettext === 'function') {
        template = window.ngettext(singular, plural, count);
    }
    if (typeof window.interpolate === 'function') {
        return window.interpolate(template, values, true);
    }
    return template.replace(/%\((\w+)\)s/g, function (match, key) {
        return String(values[key]);
    });
}

function initTrackLimits(container) {
    if (container.dataset.initialized) {
        return;
    }
    container.dataset.initialized = 'true';

    const form = container.closest('form');
    const allTracks = document.getElementById(container.dataset.allTracksId);
    const allEvents = document.getElementById(container.dataset.allEventsId);
    const eventName = container.dataset.limitEventsName;
    const eventBoxes =
        form && eventName
            ? Array.from(form.querySelectorAll(`input[type="checkbox"][name="${CSS.escape(eventName)}"]`))
            : [];
    const groups = Array.from(container.querySelectorAll('.team-track-group'));
    const totalTracks = groups.reduce(function (sum, group) {
        return sum + trackBoxes(group).length;
    }, 0);
    const warning = container.querySelector('.team-track-empty-warning');
    const summary = container.querySelector('[data-track-summary]');
    const search = container.querySelector('.team-track-search');
    const searchRow = container.querySelector('.team-track-search-row');
    const noMatch = container.querySelector('.team-track-search-empty');
    const outOfScope = container.querySelector('.team-track-out-of-scope');

    function isUnrestricted() {
        return Boolean(allTracks && allTracks.checked);
    }

    // null means "every event"; otherwise the ids of the events ticked under "Limit to events".
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

    function inScopeGroups() {
        return groups.filter(function (group) {
            return group.dataset.inScope !== 'false';
        });
    }

    function visibleGroups() {
        return groups.filter(function (group) {
            return !group.hidden;
        });
    }

    function updateCount(group) {
        const countEl = group.querySelector('[data-selection-count]');
        if (countEl) {
            const boxes = trackBoxes(group);
            countEl.textContent = `${countChecked(boxes)} / ${boxes.length}`;
        }
    }

    function updateSummary() {
        if (!summary) {
            return;
        }
        const shown = inScopeGroups();
        const boxes = shown.flatMap(trackBoxes);
        summary.hidden = isUnrestricted() || boxes.length === 0;
        if (summary.hidden) {
            summary.textContent = '';
            return;
        }
        const selected = countChecked(boxes);
        const events = shown.filter(function (group) {
            return countChecked(trackBoxes(group)) > 0;
        }).length;
        const tracksText = translate(
            '%(selected)s of %(total)s track selected',
            '%(selected)s of %(total)s tracks selected',
            boxes.length,
            { selected: selected, total: boxes.length }
        );
        summary.textContent = selected
            ? `${tracksText} ${translate('in %(events)s event', 'in %(events)s events', events, { events: events })}`
            : tracksText;
    }

    function applyFilter() {
        const needle = search ? search.value.trim().toLowerCase() : '';
        groups.forEach(function (group) {
            let matches = 0;
            group.querySelectorAll('.team-track-item').forEach(function (item) {
                const match = !needle || (item.dataset.trackName || '').includes(needle);
                item.hidden = !match;
                if (match) {
                    matches += 1;
                }
            });
            group.hidden = group.dataset.inScope === 'false' || matches === 0;
        });
        if (noMatch) {
            noMatch.hidden = !needle || inScopeGroups().length === 0 || visibleGroups().length > 0;
        }
    }

    function refresh() {
        const eventIds = accessibleEventIds();
        groups.forEach(function (group) {
            group.dataset.inScope = String(eventIds === null || eventIds.has(group.dataset.eventId));
            updateCount(group);
        });
        applyFilter();
        if (outOfScope) {
            outOfScope.hidden = inScopeGroups().length > 0;
        }
        if (searchRow) {
            searchRow.hidden = totalTracks < FILTER_MIN_TRACKS;
        }
        if (warning) {
            warning.hidden = true;
        }
        updateSummary();
    }

    container.addEventListener('click', function (event) {
        const button = event.target.closest('[data-track-select]');
        if (!button || !container.contains(button)) {
            return;
        }
        event.preventDefault();
        if (isUnrestricted()) {
            return;
        }
        const ownGroup = button.closest('.team-track-group');
        const checked = button.dataset.trackSelect === 'all';
        // Like the list itself, All / None only touch tracks that are currently shown.
        (ownGroup ? [ownGroup] : visibleGroups()).forEach(function (group) {
            group.querySelectorAll('.team-track-item:not([hidden]) input[type="checkbox"]:not(:disabled)').forEach(
                function (box) {
                    box.checked = checked;
                }
            );
            updateCount(group);
        });
        if (warning) {
            warning.hidden = true;
        }
        updateSummary();
    });

    container.addEventListener('change', function (event) {
        const group = event.target.closest('.team-track-group');
        if (group) {
            updateCount(group);
        }
        if (warning) {
            warning.hidden = true;
        }
        updateSummary();
    });

    [allTracks, allEvents].concat(eventBoxes).forEach(function (input) {
        if (input) {
            input.addEventListener('change', refresh);
        }
    });

    if (search) {
        search.addEventListener('input', function () {
            applyFilter();
            updateSummary();
        });
        // Enter in the filter must not submit the whole team form.
        search.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
            }
        });
    }

    if (form) {
        form.addEventListener('submit', function (event) {
            // offsetParent is null while the Talk permissions block is hidden.
            if (isUnrestricted() || container.offsetParent === null) {
                return;
            }
            const shown = inScopeGroups();
            const anySelected = shown.some(function (group) {
                return countChecked(trackBoxes(group)) > 0;
            });
            if (!anySelected) {
                event.preventDefault();
                if (warning) {
                    warning.hidden = false;
                    warning.scrollIntoView({ block: 'center' });
                }
            }
        });
    }

    // Browsers can restore checkbox states on reload or back navigation without change events.
    window.addEventListener('pageshow', refresh);

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
