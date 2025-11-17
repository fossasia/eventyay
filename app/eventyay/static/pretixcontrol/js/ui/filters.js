(function() {
    'use strict';

    function ready(fn) {
        if (document.readyState !== 'loading') {
            fn();
        } else {
            document.addEventListener('DOMContentLoaded', fn);
        }
    }

    ready(function() {
        setTimeout(init, 150);
    });

    function init() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        
        filterButtons.forEach(function(filterBtn) {
            if (filterBtn.dataset.initialized) return;
            filterBtn.dataset.initialized = 'true';
            
            const clearBtn = filterBtn.parentElement.querySelector('.clear-btn');
            if (!clearBtn) return;
            
            const form = filterBtn.closest('form') || 
                        filterBtn.closest('.filter-form, .row')?.querySelector('form');
            
            if (!form) return;
            
            filterBtn.type = 'button';
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            });
            
            filterBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                applyFilters(form);
                return false;
            });
            
            clearBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                clearFilters(form);
                return false;
            });
        });
    }

    function applyFilters(form) {
        const formData = new FormData(form);
        const filters = {};
        
        for (const [key, value] of formData.entries()) {
            if (value && value.trim() !== '') {
                filters[key] = value.toLowerCase();
            }
        }
        
        const rows = findFilterableRows();
        let visibleCount = 0;
        
        rows.forEach(function(row) {
            let shouldShow = true;
            
            for (const [key, value] of Object.entries(filters)) {
                const rowText = row.textContent.toLowerCase();
                if (!rowText.includes(value)) {
                    shouldShow = false;
                    break;
                }
            }
            
            if (shouldShow) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });
        
        showResultCount(visibleCount, rows.length);
        clearFormFields(form);
    }

    function clearFilters(form) {
        clearFormFields(form);
        
        const rows = findFilterableRows();
        rows.forEach(function(row) {
            row.style.display = '';
        });
        
        removeResultMessage();
    }

    function findFilterableRows() {
        const tableRows = Array.from(document.querySelectorAll('table tbody tr'));
        const listItems = Array.from(document.querySelectorAll('.list-group-item'));
        const cards = Array.from(document.querySelectorAll('.card, .panel'));
        
        return [...tableRows, ...listItems, ...cards].filter(function(el) {
            return el && !el.classList.contains('empty-collection');
        });
    }

    function clearFormFields(form) {
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(function(input) {
            if (input.type === 'checkbox' || input.type === 'radio') {
                input.checked = false;
            } else if (input.tagName === 'SELECT') {
                input.selectedIndex = 0;
                if (typeof jQuery !== 'undefined') {
                    jQuery(input).trigger('change.select2');
                }
            } else if (input.type !== 'hidden' && input.type !== 'submit') {
                input.value = '';
            }
        });
    }

    function showResultCount(visible, total) {
        removeResultMessage();
        
        if (visible === 0) {
            const msg = document.createElement('div');
            msg.className = 'alert alert-info filter-result-message';
            msg.textContent = 'No results match your filters.';
            
            const container = document.querySelector('.container-fluid') || document.body;
            const filterForm = container.querySelector('.filter-form');
            if (filterForm) {
                filterForm.parentNode.insertBefore(msg, filterForm.nextSibling);
            } else {
                container.insertBefore(msg, container.firstChild);
            }
        } else if (visible < total) {
            const msg = document.createElement('div');
            msg.className = 'alert alert-info filter-result-message';
            msg.textContent = 'Showing ' + visible + ' of ' + total + ' results.';
            
            const container = document.querySelector('.container-fluid') || document.body;
            const filterForm = container.querySelector('.filter-form');
            if (filterForm) {
                filterForm.parentNode.insertBefore(msg, filterForm.nextSibling);
            }
        }
    }

    function removeResultMessage() {
        const existing = document.querySelectorAll('.filter-result-message');
        existing.forEach(function(el) {
            el.remove();
        });
    }

})();
