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
});
