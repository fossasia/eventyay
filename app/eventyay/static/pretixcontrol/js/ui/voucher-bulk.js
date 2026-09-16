const formSelector = '[data-voucher-bulk-form]';
const tagSelector = '[name="tag"]';
const tagPrefixSelector = '[name="use_tag_as_prefix"]';

function syncPrefix(form) {
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

window.addEventListener('pageshow', () => {
    document.querySelectorAll(formSelector).forEach(syncPrefix);
});

document.querySelectorAll(formSelector).forEach(syncPrefix);
