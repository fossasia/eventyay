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
});
