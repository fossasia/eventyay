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
