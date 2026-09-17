'use strict';

function init() {
    const btn = document.getElementById('admin-test-turnstile-btn');
    if (!btn) {
        return;
    }

    const testForm = document.getElementById('admin-test-turnstile-form');
    const secretInput = document.getElementById('id_turnstile_secret_key');

    if (!testForm || !secretInput) {
        return;
    }

    btn.addEventListener('click', () => {
        const secret = secretInput.value;
        testForm.querySelector('input[name="turnstile_secret_key"]')?.remove();

        if (secret) {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'turnstile_secret_key';
            hidden.value = secret;
            testForm.appendChild(hidden);
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
