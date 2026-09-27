const formSelector = '[data-voucher-bulk-form]';
const tagSelector = '[name="tag"]';
const tagPrefixSelector = '[name="use_tag_as_prefix"]';
let hasScrolledToError = false;

function syncPrefix(form) {
    if (!form) {
        return;
    }
    const tagInput = form.querySelector(tagSelector);
    const tagPrefixInput = form.querySelector(tagPrefixSelector);
    const prefixInput = form.querySelector('#voucher-bulk-codes-prefix');
    if (!tagInput || !tagPrefixInput || !prefixInput || !tagPrefixInput.checked) {
        return;
    }

    prefixInput.value = tagInput.value.trim();
}

function formFor(target) {
    return target.closest(formSelector);
}

function scrollToError(container = document) {
    const errorEl = container.querySelector(
        `${formSelector} .alert-danger, ${formSelector} .has-error`
    );
    if (errorEl) {
        hasScrolledToError = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

document.addEventListener(
    'change',
    (event) => {
        if (event.target.matches(`${formSelector} ${tagPrefixSelector}`)) {
            syncPrefix(formFor(event.target));
        }
    },
    true
);

document.addEventListener(
    'input',
    (event) => {
        if (event.target.matches(`${formSelector} ${tagSelector}`)) {
            syncPrefix(formFor(event.target));
        }
    },
    true
);

document.addEventListener(
    'submit',
    (event) => {
        if (event.target.matches(formSelector)) {
            hasScrolledToError = false;
        }
    },
    true
);

document.addEventListener('click', async (event) => {
    const btn = event.target.closest('#voucher-bulk-codes-generate');
    if (!btn) {
        return;
    }
    const form = formFor(btn);
    if (!form) {
        return;
    }
    const numInput = form.querySelector('#voucher-bulk-codes-num');
    const prefixInput = form.querySelector('#voucher-bulk-codes-prefix');
    const codesInput = form.querySelector('#id_codes');
    const formGroup = numInput ? numInput.closest('.form-group') : null;
    const num = numInput ? numInput.value.trim() : '';
    const prefix = prefixInput ? prefixInput.value.trim() : '';

    if (num !== '') {
        const url = btn.getAttribute('data-rng-url');
        if (codesInput) {
            codesInput.value = window.gettext ? window.gettext('Generating...') : 'Generating...';
        }
        if (formGroup) {
            formGroup.classList.remove('has-error');
        }
        try {
            const query = new URLSearchParams({ num, prefix });
            const response = await fetch(`${url}?${query.toString()}`);
            if (!response.ok) {
                throw new Error(`RNG request failed with status: ${response.status}`);
            }
            const data = await response.json();
            if (codesInput && Array.isArray(data.codes)) {
                codesInput.value = data.codes.join('\n');
            }
        } catch (err) {
            console.error('Error generating voucher codes:', err);
            alert(window.gettext ? window.gettext('Error while generating keys.') : 'Error while generating keys.');
        }
    } else {
        if (formGroup) {
            formGroup.classList.add('has-error');
        }
        if (numInput) {
            numInput.focus();
        }
        setTimeout(() => {
            if (formGroup) {
                formGroup.classList.remove('has-error');
            }
        }, 3000);
    }
});

const observer = new MutationObserver(() => {
    document.querySelectorAll(formSelector).forEach(syncPrefix);
    if (!hasScrolledToError) {
        scrollToError();
    }
});

if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
} else {
    document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, { childList: true, subtree: true });
    });
}

window.addEventListener('pageshow', () => {
    document.querySelectorAll(formSelector).forEach(syncPrefix);
    scrollToError();
});

document.querySelectorAll(formSelector).forEach(syncPrefix);
scrollToError();
