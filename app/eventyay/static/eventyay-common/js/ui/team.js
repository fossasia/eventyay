document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.team-review-settings').forEach(function (settingsDiv) {
        const reviewToggleId = settingsDiv.getAttribute('data-review-toggle');
        const submissionToggleId = settingsDiv.getAttribute('data-submission-toggle');

        const reviewCheckbox = reviewToggleId ? document.getElementById(reviewToggleId) : null;
        const submissionCheckbox = submissionToggleId ? document.getElementById(submissionToggleId) : null;

        if (!reviewCheckbox && !submissionCheckbox) return;

        function toggle() {
            const visible = (reviewCheckbox && reviewCheckbox.checked) ||
                            (submissionCheckbox && submissionCheckbox.checked);
            settingsDiv.style.display = visible ? '' : 'none';
        }

        if (reviewCheckbox) reviewCheckbox.addEventListener('change', toggle);
        if (submissionCheckbox) submissionCheckbox.addEventListener('change', toggle);
        toggle();
    });

    document.querySelectorAll('.team-exhibition-permissions').forEach(function (container) {
        const eventIds = (container.getAttribute('data-exhibition-events') || '')
            .split(',')
            .filter(Boolean);
        const allEventsId = container.getAttribute('data-all-events-id');
        const limitEventsName = container.getAttribute('data-limit-events-name');

        const allEvents = allEventsId ? document.getElementById(allEventsId) : null;
        const limitEvents = limitEventsName
            ? document.querySelectorAll('input[name="' + limitEventsName + '"]')
            : [];
        const permissions = container.querySelectorAll('input[type="checkbox"]');

        if (!allEvents && limitEvents.length === 0) return;

        function appliesToSelection() {
            if (eventIds.length === 0) return false;
            if (allEvents && allEvents.checked) return true;
            return Array.from(limitEvents).some(function (input) {
                return input.checked && eventIds.indexOf(input.value) !== -1;
            });
        }

        function toggle(clearHidden) {
            const visible = appliesToSelection();
            container.style.display = visible ? '' : 'none';
            if (!visible && clearHidden) {
                permissions.forEach(function (permission) {
                    permission.checked = false;
                });
            }
        }

        if (allEvents) {
            allEvents.addEventListener('change', function () { toggle(true); });
        }
        limitEvents.forEach(function (input) {
            input.addEventListener('change', function () { toggle(true); });
        });
        toggle(false);
    });

    document.querySelectorAll('.team-permission-children').forEach(function (container) {
        const parentId = container.getAttribute('data-parent');
        const parent = document.getElementById(parentId);
        if (!parent) return;

        const children = container.querySelectorAll('input[type="checkbox"]');

        function syncFromParent() {
            const enabled = parent.checked;
            children.forEach(function (child) {
                child.disabled = !enabled;
                if (!enabled) {
                    child.checked = false;
                }
            });
            container.classList.toggle('team-permission-children--disabled', !enabled);
        }

        function syncFromChild() {
            if (Array.from(children).some(function (child) { return child.checked; })) {
                parent.checked = true;
            }
        }

        parent.addEventListener('change', syncFromParent);
        children.forEach(function (child) {
            child.addEventListener('change', syncFromChild);
        });
        syncFromChild();
        syncFromParent();
    });
});
