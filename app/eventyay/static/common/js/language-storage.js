'use strict';

// Store user language preference and handle language selector changes

// Store language in localStorage for client-side access
try {
    const langElement = document.getElementById('user-language-code');
    if (langElement) {
        const lang = langElement.dataset.lang;
        if (lang) {
            localStorage.setItem('userLanguage', lang);
        }
    }
} catch (e) {
    // Ignore storage errors (e.g., private browsing mode)
}

// Handle language selector form submission
const select = document.getElementById('navbar-language-select');
if (select && select.form) {
    select.addEventListener('change', function () {
        select.form.submit();
    });
}
