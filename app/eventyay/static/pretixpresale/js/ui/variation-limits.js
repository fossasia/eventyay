/*
 * Limit how many variations of a product can be chosen in one order,
 * based on data-variation-max-total on the product's <details> element.
 */
const DETAILS_SELECTOR = 'details.item-with-variations[data-variation-max-total]';

// Only the selected quantities count towards the limit: the checkboxes and the quantity inputs.
// Other number inputs, such as the price of a pay-what-you-want variation, are not counted or changed.
const variationInputs = (details) => [
    ...details.querySelectorAll('.variations input[type=checkbox], .variations input.input-product-count'),
];

const selectedAmount = (input) => {
    if (input.type === 'checkbox') {
        return input.checked ? 1 : 0;
    }
    // Number() reads the whole value, so "1e3" counts as 1000 and not as 1 like parseInt() would.
    const value = Number(input.value || 0);
    return Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;
};

const selectionTotal = (details) =>
    variationInputs(details).reduce((total, input) => total + selectedAmount(input), 0);

// Django's JavaScript catalog defines gettext, ngettext and interpolate on window. If it is missing,
// the message is shown in English, so the limit keeps working.
const limitMessage = (details, maxTotal) => {
    const defaultName = typeof window.gettext === 'function' ? window.gettext('this product') : 'this product';
    const productName = (details.getAttribute('data-product-name') || defaultName).trim();
    if (typeof window.ngettext !== 'function' || typeof window.interpolate !== 'function') {
        return `You can only choose a maximum of ${maxTotal} option${maxTotal === 1 ? '' : 's'} for ${productName}.`;
    }
    return window.interpolate(
        window.ngettext(
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

// Shows the message on an input that was set back within the limit. Browsers hide the message as soon as
// the input is valid again, so it stays invalid only until the visitor's next action: pressing the mouse or
// a key, or leaving the input. The corrected input therefore never blocks the order.
const showCorrection = (input, message) => {
    showValidity(input, message);
    const done = new AbortController();
    const clear = () => {
        input.setCustomValidity('');
        done.abort();
    };
    input.addEventListener('blur', clear, { signal: done.signal });
    input.addEventListener('keydown', clear, { signal: done.signal });
    document.addEventListener('pointerdown', clear, { signal: done.signal });
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
        // Setting the value does not fire change, so fire it for main.js to update the order button.
        // It runs this check again, which clears the messages, so the message is shown afterwards.
        changedInput.dispatchEvent(new Event('change', { bubbles: true }));
        showCorrection(changedInput, message);
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
