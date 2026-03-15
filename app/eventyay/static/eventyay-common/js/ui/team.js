document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.team-review-settings').forEach(function (settingsDiv) {
        var toggleId = settingsDiv.getAttribute('data-review-toggle');
        if (!toggleId) return;

        var checkbox = document.getElementById(toggleId);
        if (!checkbox) return;

        function toggle() {
            settingsDiv.style.display = checkbox.checked ? '' : 'none';
        }

        checkbox.addEventListener('change', toggle);
        toggle();
    });
});
