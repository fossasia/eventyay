/*
 * Limit how many variations of a product can be chosen in one order,
 * based on data-variation-max-total on the product's <details> element.
 */
const DETAILS_SELECTOR = 'details.item-with-variations[data-variation-max-total]';

// Only the selected quantities count towards the limit. Pay-what-you-want variations
// also have a number input for the price, which must not be counted or changed here.
const variationInputs = (details) => [
    ...details.querySelectorAll(
        '.variations input[type=checkbox], .variations input[type=number]:not(.input-product-price)'
    ),
];

const selectedAmount = (input) => {
    if (input.type === 'checkbox') {
        return input.checked ? 1 : 0;
    }
    const value = parseInt(input.value || '0', 10);
    return Number.isNaN(value) || value < 0 ? 0 : value;
};

const selectionTotal = (details) =>
    variationInputs(details).reduce((total, input) => total + selectedAmount(input), 0);

const limitMessage = (details, maxTotal) => {
    const productName = (details.getAttribute('data-product-name') || gettext('this product')).trim();
    return interpolate(
        ngettext(
            'You can only choose a maximum of %(max)s option for %(product)s.',
            'You can only choose a maximum of %(max)s options for %(product)s.',
            maxTotal
        ),
        { max: maxTotal, product: productName },
        true
    );
};

const clearValidity = (details) => {
    variationInputs(details).forEach((input) => input.setCustomValidity(''));
};

const showValidity = (input, message) => {
    if (!input) {
        return;
    }
    input.setCustomValidity(message);
    input.reportValidity();
};

const showVariations = (details) => {
    details.open = true;
    details.classList.add('details-open');
    for (const child of details.children) {
        if (child.tagName !== 'SUMMARY') {
            child.style.display = '';
        }
    }
    details.querySelectorAll('a.variation-toggle[data-hide-label]').forEach((toggle) => {
        const label = toggle.querySelector('.variation-toggle-label');
        if (label) {
            label.textContent = toggle.getAttribute('data-hide-label');
        }
        toggle.setAttribute('aria-expanded', 'true');
    });
};

// Returns false and shows a message if more variations are chosen than allowed.
// If the limit was passed by changing changedInput, that input is set back to the most it allows.
const enforceMaximum = (details, changedInput) => {
    clearValidity(details);

    const maxTotal = parseInt(details.getAttribute('data-variation-max-total') || '0', 10);
    if (!maxTotal || maxTotal < 1) {
        return true;
    }

    const total = selectionTotal(details);
    if (total <= maxTotal) {
        return true;
    }

    const message = limitMessage(details, maxTotal);
    showVariations(details);

    if (changedInput) {
        if (changedInput.type === 'checkbox') {
            changedInput.checked = false;
        } else {
            const allowed = maxTotal - (total - selectedAmount(changedInput));
            changedInput.value = String(Math.max(0, allowed));
        }
        showValidity(changedInput, message);
        return false;
    }

    showValidity(variationInputs(details).find((input) => selectedAmount(input) > 0), message);
    return false;
};

document.querySelectorAll(DETAILS_SELECTOR).forEach((details) => {
    variationInputs(details).forEach((input) => {
        const onChange = () => enforceMaximum(details, input);
        input.addEventListener('change', onChange);
        input.addEventListener('input', onChange);
    });
});

document.querySelectorAll('form').forEach((form) => {
    const limitedProducts = [...form.querySelectorAll(DETAILS_SELECTOR)];
    if (!limitedProducts.length) {
        return;
    }
    form.addEventListener('submit', (event) => {
        if (!limitedProducts.every((details) => enforceMaximum(details, null))) {
            // Also keep the cart's async submit handler on <body> from sending the form.
            event.preventDefault();
            event.stopPropagation();
        }
    });
});
