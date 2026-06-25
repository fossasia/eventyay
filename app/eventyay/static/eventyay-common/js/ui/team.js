document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.team-review-settings').forEach(function (settingsDiv) {
        const toggleId = settingsDiv.getAttribute('data-review-toggle');
        if (!toggleId) return;

        const checkbox = document.getElementById(toggleId);
        if (!checkbox) return;

        function toggle() {
            settingsDiv.style.display = checkbox.checked ? '' : 'none';
        }

        checkbox.addEventListener('change', toggle);
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
