/**
 * Report mode toggle for the order overview page.
 */
function initOrderOverviewReport(root = document) {
    const toggleRoot = root.querySelector('[data-order-overview-report]');
    if (!toggleRoot) {
        return;
    }

    const buttons = toggleRoot.querySelectorAll('[data-report-mode]');
    const table = toggleRoot.querySelector('.table-product-overview');
    if (!buttons.length || !table) {
        return;
    }

    const setMode = (target) => {
        toggleRoot.dataset.reportMode = target;
        buttons.forEach((button) => {
            const isActive = button.dataset.reportMode === target;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        const heading = toggleRoot.querySelector('[data-report-table-heading]');
        if (heading) {
            const labels = {
                '.count': heading.dataset.headingSales,
                '.sum-gross': heading.dataset.headingGross,
                '.sum-net': heading.dataset.headingNet,
            };
            heading.textContent = labels[target] || labels['.count'];
        }

        const tooltipIcon = toggleRoot.querySelector('#report-table-tooltip');
        if (tooltipIcon) {
            const tooltips = {
                '.count': tooltipIcon.dataset.tooltipSales,
                '.sum-gross': tooltipIcon.dataset.tooltipGross,
                '.sum-net': tooltipIcon.dataset.tooltipNet,
            };
            const newTooltip = tooltips[target] || tooltips['.count'];
            tooltipIcon.setAttribute('data-original-title', newTooltip);
            tooltipIcon.setAttribute('title', newTooltip);
        }
    };

    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            setMode(button.dataset.reportMode);
        });
    });

    const activeButton = toggleRoot.querySelector('[data-report-mode].active') || buttons[0];
    if (activeButton) {
        setMode(activeButton.dataset.reportMode);
    }

    // Toggle classification rows
    if (table) {
        const classifications = table.querySelectorAll('tr.classification');
        classifications.forEach(row => {
            // Make it look clickable
            row.style.cursor = 'pointer';
            
            row.addEventListener('click', (e) => {
                // Ignore clicks on links inside the row
                if (e.target.tagName.toLowerCase() === 'a') return;

                const icon = row.querySelector('.order-overview-group-icon');
                let isCollapsing = false;
                
                // Determine state from the first row below this classification
                let checkRow = row.nextElementSibling;
                if (checkRow && !checkRow.classList.contains('classification') && !checkRow.classList.contains('total')) {
                    isCollapsing = checkRow.style.display !== 'none';
                }

                if (icon) {
                    icon.style.transform = isCollapsing ? 'rotate(-90deg)' : 'rotate(0deg)';
                }
                
                let nextRow = row.nextElementSibling;
                while (nextRow && !nextRow.classList.contains('classification') && !nextRow.classList.contains('total')) {
                    // Use jQuery for smooth fade toggle if available
                    if (window.jQuery) {
                        window.jQuery(nextRow).fadeToggle(150);
                    } else {
                        nextRow.style.display = isCollapsing ? 'none' : '';
                    }
                    nextRow = nextRow.nextElementSibling;
                }
            });
        });
    }

    // Open the datepicker when the calendar addon is clicked.
    toggleRoot.querySelectorAll('.order-overview-filter-field .input-group.date').forEach((group) => {
        const input = group.querySelector('.datepickerfield');
        const addon = group.querySelector('.input-group-addon');
        if (!input || !addon) {
            return;
        }
        addon.addEventListener('click', () => {
            input.focus();
            if (window.jQuery) {
                const picker = window.jQuery(input).data('DateTimePicker');
                if (picker && typeof picker.show === 'function') {
                    picker.show();
                }
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initOrderOverviewReport();
});

export { initOrderOverviewReport };
