export function initHeaderPresetCategoryFilter() {
    const select = document.getElementById('headerPresetCategoryFilter');
    if (!select) {
        return;
    }

    const cards = document.querySelectorAll('.preset-admin-card');
    const emptyMsg = document.getElementById('presetCategoryEmptyMsg');
    const grid = document.getElementById('presetAdminGrid');
    const actionsGroup = document.getElementById('selectedCategoryActions');
    const editBtn = document.getElementById('editCategoryBtn');
    const deleteBtn = document.getElementById('deleteCategoryBtn');

    function filterPresets() {
        const selectedVal = select.value;
        const selectedOption = select.options[select.selectedIndex];
        let visibleCount = 0;

        cards.forEach((card) => {
            const catId = card.getAttribute('data-category-id');
            if (selectedVal === 'all' || catId === selectedVal) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        if (emptyMsg && grid) {
            if (visibleCount === 0 && cards.length > 0) {
                emptyMsg.style.display = '';
                grid.style.display = 'none';
            } else {
                emptyMsg.style.display = 'none';
                grid.style.display = '';
            }
        }

        if (actionsGroup && editBtn && deleteBtn) {
            if (selectedVal !== 'all' && selectedOption) {
                const editUrl = selectedOption.getAttribute('data-edit-url');
                const deleteUrl = selectedOption.getAttribute('data-delete-url');
                if (editUrl) editBtn.setAttribute('href', editUrl);
                if (deleteUrl) deleteBtn.setAttribute('href', deleteUrl);
                actionsGroup.style.display = 'flex';
            } else {
                actionsGroup.style.display = 'none';
            }
        }

        const url = new URL(window.location);
        if (selectedVal === 'all') {
            url.searchParams.delete('category');
        } else {
            url.searchParams.set('category', selectedVal);
        }
        window.history.replaceState(null, '', url.toString());
    }

    select.addEventListener('change', filterPresets);
    filterPresets();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeaderPresetCategoryFilter);
} else {
    initHeaderPresetCategoryFilter();
}
