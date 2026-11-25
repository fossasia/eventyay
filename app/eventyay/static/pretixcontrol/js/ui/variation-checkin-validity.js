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

function initVariationCheckinValidity(root = document) {
    root.querySelectorAll('.variation-checkin-validity').forEach((block) => {
        if (block.dataset.checkinToggleBound === '1') {
            return;
        }
        block.dataset.checkinToggleBound = '1';
        const toggle = block.querySelector('.variation-checkin-toggle');
        if (!toggle) {
            return;
        }
        toggle.setAttribute('role', 'button');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.addEventListener('click', (event) => {
            event.preventDefault();
            const fields = block.querySelector('.variation-checkin-fields');
            setExpanded(block, Boolean(fields && fields.hidden));
        });
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
