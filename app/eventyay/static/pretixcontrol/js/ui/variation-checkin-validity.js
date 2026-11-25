/**
 * Toggle collapsed check-in validity fields on the product variation form.
 */

function setExpanded(root, expanded) {
    const fields = root.querySelector('.variation-checkin-fields');
    const toggle = root.querySelector('.variation-checkin-toggle');
    const label = root.querySelector('.variation-checkin-label');
    const caret = root.querySelector('.variation-checkin-caret');
    if (!fields || !toggle) {
        return;
    }
    fields.hidden = !expanded;
    if (label) {
        label.textContent = expanded
            ? (toggle.dataset.labelHide || 'Hide check-in settings')
            : (toggle.dataset.labelShow || 'Edit check-in settings');
    }
    if (caret) {
        caret.textContent = expanded ? '▲' : '▼';
    }
    toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
}

function updateSummary(block) {
    const select = block.querySelector('select[name$="-admission_validity_mode"]');
    const summary = block.querySelector('.variation-checkin-summary-text');
    if (!select || !summary) {
        return;
    }
    const option = select.options[select.selectedIndex];
    if (!option) {
        return;
    }
    if (option.value === 'inherit') {
        summary.textContent = block.dataset.inheritSummary || option.textContent.trim();
    } else {
        summary.textContent = option.textContent.trim();
    }
}

function fieldsHaveErrors(fields) {
    if (!fields) {
        return false;
    }
    return Boolean(
        fields.querySelector('.has-error, .is-invalid, .alert-danger, [aria-invalid="true"]')
    );
}

function initVariationCheckinValidity(root = document) {
    root.querySelectorAll('.variation-checkin-validity').forEach((block) => {
        if (block.dataset.checkinToggleBound === '1') {
            return;
        }
        block.dataset.checkinToggleBound = '1';
        const toggle = block.querySelector('.variation-checkin-toggle');
        const fields = block.querySelector('.variation-checkin-fields');
        const modeSelect = block.querySelector('select[name$="-admission_validity_mode"]');
        if (!toggle) {
            return;
        }
        toggle.setAttribute('role', 'button');
        if (fieldsHaveErrors(fields) || (fields && !fields.hidden)) {
            setExpanded(block, true);
        } else {
            toggle.setAttribute('aria-expanded', 'false');
        }
        updateSummary(block);
        toggle.addEventListener('click', (event) => {
            event.preventDefault();
            const panel = block.querySelector('.variation-checkin-fields');
            const expanding = Boolean(panel && panel.hidden);
            if (!expanding) {
                updateSummary(block);
            }
            setExpanded(block, expanding);
        });
        if (modeSelect) {
            modeSelect.addEventListener('change', () => updateSummary(block));
        }
    });
}

function observeFormsetAdds() {
    document.querySelectorAll('[data-formset-body]').forEach((body) => {
        const observer = new MutationObserver(() => initVariationCheckinValidity(body));
        observer.observe(body, { childList: true });
    });
}

function boot() {
    initVariationCheckinValidity();
    observeFormsetAdds();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
} else {
    boot();
}

export { initVariationCheckinValidity };
