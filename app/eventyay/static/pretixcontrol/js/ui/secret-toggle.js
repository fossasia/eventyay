;(function () {
    'use strict';

    document.addEventListener('click', function (e) {
        var button = e.target.closest('.secret-toggle');
        if (!button) return;

        e.preventDefault();

        var input = button.parentElement.querySelector('input[type="password"], input[type="text"]');
        var icon = button.querySelector('i');
        if (!input || !icon) return;

        var showLabel = button.dataset.labelShow || 'Show secret key';
        var hideLabel = button.dataset.labelHide || 'Hide secret key';

        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
            button.setAttribute('aria-pressed', 'true');
            button.setAttribute('aria-label', hideLabel);
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
            button.setAttribute('aria-pressed', 'false');
            button.setAttribute('aria-label', showLabel);
        }
    });
}());