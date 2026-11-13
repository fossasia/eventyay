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

function translate(singular, plural, count, values) {
    const template =
        typeof window.ngettext === 'function'
            ? window.ngettext(singular, plural, count)
            : count === 1
              ? singular
              : plural;
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
    const scope = form || document;
    const allTracks = document.getElementById(container.dataset.allTracksId);
    const allEvents = document.getElementById(container.dataset.allEventsId);
    const eventBoxes = Array.from(
        scope.querySelectorAll(`input[name="${CSS.escape(container.dataset.limitEventsName || '')}"]`)
    );
    const groups = Array.from(container.querySelectorAll('.team-track-group'));
    const outOfScope = container.querySelector('.team-track-out-of-scope');
    const warning = container.querySelector('.team-track-empty-warning');
    const summary = container.querySelector('[data-track-summary]');
    const search = container.querySelector('.team-track-search');
    const searchRow = container.querySelector('.team-track-search-row');
    const noMatch = container.querySelector('.team-track-search-empty');
    const bulkActions = container.querySelector('.team-track-bulk-actions');
    const totalTracks = groups.reduce(function (sum, group) {
        return sum + trackBoxes(group).length;
    }, 0);

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

    function updateSummary() {
        if (!summary) {
            return;
        }
        const shown = inScopeGroups();
        const boxes = shown.flatMap(trackBoxes);
        const selected = boxes.filter(function (box) {
            return box.checked;
        }).length;
        const events = shown.filter(function (group) {
            return trackBoxes(group).some(function (box) {
                return box.checked;
            });
        }).length;
        const tracksText = translate(
            '%(selected)s of %(total)s track selected',
            '%(selected)s of %(total)s tracks selected',
            boxes.length,
            { selected: selected, total: boxes.length }
        );
        const eventsText = translate(
            'in %(events)s event',
            'in %(events)s events',
            events,
            { events: events }
        );
        summary.textContent = selected ? `${tracksText} ${eventsText}` : tracksText;
        summary.hidden = boxes.length === 0;
    }

    function refresh() {
        container.hidden = Boolean(allTracks && allTracks.checked);
        const eventIds = accessibleEventIds();
        groups.forEach(function (group) {
            const inScope = eventIds === null || eventIds.has(group.dataset.eventId);
            group.dataset.inScope = String(inScope);
            trackBoxes(group).forEach(function (box) {
                box.disabled = !inScope;
            });
            updateCount(group);
        });
        applyFilter();
        if (outOfScope) {
            outOfScope.hidden = inScopeGroups().length > 0;
        }
        if (bulkActions) {
            bulkActions.hidden = inScopeGroups().length === 0;
        }
        if (searchRow) {
            searchRow.hidden = totalTracks < 8;
        }
        if (warning) {
            warning.hidden = true;
        }
        updateSummary();
    }

    container.addEventListener('click', function (event) {
        const trigger = event.target.closest('[data-track-select]');
        if (!trigger || !container.contains(trigger)) {
            return;
        }
        event.preventDefault();
        const ownGroup = trigger.closest('.team-track-group');
        const targets = ownGroup ? [ownGroup] : visibleGroups();
        const checked = trigger.dataset.trackSelect === 'all';
        targets.forEach(function (group) {
            group.querySelectorAll('.team-track-item:not([hidden]) input[type="checkbox"]').forEach(function (box) {
                box.checked = checked;
            });
            updateCount(group);
        });
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
        search.addEventListener('input', applyFilter);
        search.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
            }
        });
    }

    if (form) {
        form.addEventListener('submit', function (event) {
            const restricting = allTracks && !allTracks.checked && container.offsetParent !== null;
            if (!restricting) {
                return;
            }
            const anySelected = inScopeGroups().some(function (group) {
                return trackBoxes(group).some(function (box) {
                    return box.checked;
                });
            });
            if (!anySelected && inScopeGroups().length > 0) {
                event.preventDefault();
                if (warning) {
                    warning.hidden = false;
                    warning.scrollIntoView({ block: 'center' });
                }
            }
        });
    }

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
