/**
 * Toggle the advanced filters panel on the organiser orders list.
 */

function setExpanded(root, expanded) {
    const toggle = root.querySelector('[data-orders-filters-toggle]');
    const panel = root.querySelector('[data-orders-advanced-filters]');
    const goForm = root.querySelector('[data-orders-go-form]');

    if (!toggle || !panel) {
        return;
    }

    toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    panel.hidden = !expanded;
    panel.classList.toggle('is-collapsed', !expanded);

    if (goForm) {
        goForm.hidden = !expanded;
        goForm.classList.toggle('is-collapsed', !expanded);
    }
}

function initOrdersFilter(root = document) {
    const searchRoots = root.querySelectorAll('[data-orders-search]');
    searchRoots.forEach((searchRoot) => {
        const toggle = searchRoot.querySelector('[data-orders-filters-toggle]');
        if (!toggle || toggle.dataset.ordersFilterBound === '1') {
            return;
        }
        toggle.dataset.ordersFilterBound = '1';

        toggle.addEventListener('click', () => {
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            setExpanded(searchRoot, !expanded);
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initOrdersFilter());
} else {
    initOrdersFilter();
}

export { initOrdersFilter, setExpanded };
