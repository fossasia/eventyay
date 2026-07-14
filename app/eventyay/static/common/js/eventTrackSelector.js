/**
 * Event-track selector for Team permissions.
 *
 * Provides interactive filtering of tracks by event using a dropdown,
 * selection counts, per-event search for long track lists, and
 * "Select all" / "Select none" helpers.
 *
 * Expected DOM structure (per selector):
 *   .event-track-selector
 *     select.event-track-filter
 *     .event-tracks-placeholder
 *     .event-track-group[data-event-group-id]
 *       .event-track-search (optional)
 *       .event-track-item[data-track-name]
 *       [data-selection-count]
 *       .track-select-all[data-event-id]
 *       .track-select-none[data-event-id]
 */

const COUNT_LABELS = {
    noneSelected: '0 / {total}',
    selected: '{selected} / {total}',
};

function formatCount(selected, total) {
    const template = selected === 0 ? COUNT_LABELS.noneSelected : COUNT_LABELS.selected;
    return template
        .replace('{selected}', String(selected))
        .replace('{total}', String(total));
}

function updateOptionLabels(select) {
    const container = select.closest('.event-track-selector');
    if (!container) {
        return;
    }
    Array.from(select.options).forEach(function (option) {
        if (!option.value) {
            return;
        }
        const base = option.dataset.baseLabel || option.textContent.trim();
        const total = Number(option.dataset.trackCount || 0);
        if (total === 0) {
            const emptyLabel = option.dataset.noTracksLabel || 'no tracks';
            option.textContent = `${base} — ${emptyLabel}`;
            return;
        }
        const group = container.querySelector(`[data-event-group-id="${option.value}"]`);
        const selected = group
            ? group.querySelectorAll('input[type="checkbox"]:checked').length
            : 0;
        option.textContent = `${base} — ${selected} / ${total}`;
    });
}

function updateGroupCount(group) {
    const countEl = group.querySelector('[data-selection-count]');
    if (!countEl) {
        return;
    }
    const total = Number(countEl.dataset.total || 0);
    if (total === 0) {
        countEl.textContent = '';
        return;
    }
    const selected = group.querySelectorAll('input[type="checkbox"]:checked').length;
    countEl.textContent = formatCount(selected, total);
}

function filterTracks(group, query) {
    const needle = query.trim().toLowerCase();
    let visible = 0;
    group.querySelectorAll('.event-track-item').forEach(function (item) {
        const name = item.dataset.trackName || item.textContent.toLowerCase();
        const match = !needle || name.includes(needle);
        item.hidden = !match;
        if (match) {
            visible += 1;
        }
    });
    const empty = group.querySelector('.event-track-search-empty');
    if (empty) {
        empty.hidden = visible !== 0 || !needle;
    }
}

function showEventGroup(container, selectedEventId) {
    const placeholder = container.querySelector('.event-tracks-placeholder');
    const groups = container.querySelectorAll('.event-track-group');

    groups.forEach(function (group) {
        group.hidden = true;
    });

    if (selectedEventId) {
        if (placeholder) {
            placeholder.hidden = true;
        }
        const targetGroup = container.querySelector(
            `[data-event-group-id="${selectedEventId}"]`
        );
        if (targetGroup) {
            targetGroup.hidden = false;
            updateGroupCount(targetGroup);
        }
    } else if (placeholder) {
        placeholder.hidden = false;
    }
}

function initSelector(select) {
    if (select.dataset.initialized) {
        return;
    }
    select.dataset.initialized = 'true';

    const container = select.closest('.event-track-selector');
    if (!container) {
        console.error('eventTrackSelector: missing .event-track-selector ancestor');
        return;
    }

    select.addEventListener('change', function () {
        showEventGroup(container, this.value);
    });

    container.querySelectorAll('.track-select-all').forEach(function (button) {
        button.addEventListener('click', function () {
            const eventId = this.getAttribute('data-event-id');
            const group = container.querySelector(`[data-event-group-id="${eventId}"]`);
            if (!group) {
                return;
            }
            group.querySelectorAll('.event-track-item:not([hidden]) input[type="checkbox"]').forEach(
                function (checkbox) {
                    checkbox.checked = true;
                }
            );
            updateGroupCount(group);
            updateOptionLabels(select);
        });
    });

    container.querySelectorAll('.track-select-none').forEach(function (button) {
        button.addEventListener('click', function () {
            const eventId = this.getAttribute('data-event-id');
            const group = container.querySelector(`[data-event-group-id="${eventId}"]`);
            if (!group) {
                return;
            }
            group.querySelectorAll('input[type="checkbox"]').forEach(function (checkbox) {
                checkbox.checked = false;
            });
            updateGroupCount(group);
            updateOptionLabels(select);
        });
    });

    container.querySelectorAll('.event-track-search').forEach(function (input) {
        input.addEventListener('input', function () {
            const group = input.closest('.event-track-group');
            if (group) {
                filterTracks(group, input.value);
            }
        });
    });

    container.querySelectorAll('.event-track-group').forEach(function (group) {
        group.addEventListener('change', function (event) {
            if (event.target && event.target.matches('input[type="checkbox"]')) {
                updateGroupCount(group);
                updateOptionLabels(select);
            }
        });
        updateGroupCount(group);
    });

    updateOptionLabels(select);

    // Prefer showing an event that already has track selections; otherwise auto-select
    // when there is only one event.
    const groups = Array.from(container.querySelectorAll('.event-track-group'));
    const withSelection = groups.find(function (group) {
        return group.querySelectorAll('input[type="checkbox"]:checked').length > 0;
    });
    if (withSelection) {
        select.value = withSelection.getAttribute('data-event-group-id');
        showEventGroup(container, select.value);
    } else if (select.options.length === 2) {
        select.selectedIndex = 1;
        showEventGroup(container, select.value);
    }
}

function initEventTrackSelectors(root = document) {
    root.querySelectorAll('.event-track-filter').forEach(initSelector);
}

initEventTrackSelectors();

document.addEventListener('DOMContentLoaded', function () {
    initEventTrackSelectors();
});

document.addEventListener('shown.bs.collapse', function () {
    initEventTrackSelectors();
});

export { initEventTrackSelectors };
