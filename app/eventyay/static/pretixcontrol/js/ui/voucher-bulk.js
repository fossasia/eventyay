const formSelector = '[data-voucher-bulk-form]';
const tagSelector = '[name="tag"]';
const tagPrefixSelector = '[name="use_tag_as_prefix"]';
let hasScrolledToError = false;
let currentRequestId = 0;
let isSubmitting = false;

function syncPrefix(form, preserveExisting = false) {
    if (!form) {
        return;
    }
    const tagInput = form.querySelector(tagSelector);
    const tagPrefixInput = form.querySelector(tagPrefixSelector);
    const prefixInput = form.querySelector('#voucher-bulk-codes-prefix');
    if (
        !tagInput ||
        !tagPrefixInput ||
        !prefixInput ||
        !tagPrefixInput.checked ||
        (preserveExisting && prefixInput.value.trim() !== '')
    ) {
        return;
    }

    prefixInput.value = tagInput.value.trim();
}

function formFor(target) {
    return target.closest(formSelector);
}

function scrollToError(container = document) {
    if (isSubmitting) {
        return;
    }
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
            syncPrefix(formFor(event.target), false);
        }
    },
    true
);

document.addEventListener(
    'input',
    (event) => {
        if (event.target.matches(`${formSelector} ${tagSelector}`)) {
            syncPrefix(formFor(event.target), false);
        }
    },
    true
);

document.addEventListener(
    'submit',
    (event) => {
        if (event.target.matches(formSelector)) {
            const form = event.target;
            hasScrolledToError = false;
            isSubmitting = true;
            form.querySelectorAll('.alert-danger').forEach((el) => el.remove());
            form.querySelectorAll('.has-error').forEach((el) => el.classList.remove('has-error'));
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
    let num = numInput ? numInput.value.trim() : '';
    const prefix = prefixInput ? prefixInput.value.trim() : '';

    // If quantity is left empty, default to 5 (matching backend default)
    if (num === '') {
        num = '5';
        if (numInput) {
            numInput.value = '5';
        }
    }

    if (Number.isInteger(Number(num)) && Number(num) > 0) {
        const url = btn.getAttribute('data-rng-url');
        const requestId = ++currentRequestId;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = window.gettext ? window.gettext('Generating...') : 'Generating...';

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
            if (requestId !== currentRequestId) {
                return;
            }
            if (codesInput && Array.isArray(data.codes)) {
                codesInput.value = data.codes.join('\n');
            }
        } catch (err) {
            if (requestId !== currentRequestId) {
                return;
            }
            console.error('Error generating voucher codes:', err);
            alert(window.gettext ? window.gettext('Error while generating keys.') : 'Error while generating keys.');
        } finally {
            if (requestId === currentRequestId) {
                btn.textContent = originalText;
                btn.disabled = false;
            }
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

const observer = new MutationObserver((mutations) => {
    let formOrWrapperMutated = false;
    for (const mutation of mutations) {
        if (
            mutation.target.closest &&
            (mutation.target.closest(formSelector) || mutation.target.closest('#page-wrapper'))
        ) {
            formOrWrapperMutated = true;
            break;
        }
        for (const node of mutation.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE) {
                if (node.matches(formSelector) || node.querySelector(formSelector)) {
                    formOrWrapperMutated = true;
                    break;
                }
            }
        }
        if (formOrWrapperMutated) break;
    }

    if (formOrWrapperMutated) {
        isSubmitting = false;
        document.querySelectorAll(formSelector).forEach((form) => syncPrefix(form, true));
        if (!hasScrolledToError) {
            scrollToError();
        }
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
    isSubmitting = false;
    document.querySelectorAll(formSelector).forEach((form) => syncPrefix(form, true));
    scrollToError();
});

document.querySelectorAll(formSelector).forEach((form) => syncPrefix(form, true));
scrollToError();
