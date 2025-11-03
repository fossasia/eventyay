/**
 * Client-side filtering without page reloads
 * Filters visible content based on form values
 */
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
        console.log('Found filter buttons:', filterButtons.length);
        
        filterButtons.forEach(function(filterBtn) {
            if (filterBtn.dataset.initialized) return;
            filterBtn.dataset.initialized = 'true';
            
            const clearBtn = filterBtn.parentElement.querySelector('.clear-btn');
            if (!clearBtn) {
                console.warn('Clear button not found');
                return;
            }
            
            const form = filterBtn.closest('form') || 
                        filterBtn.closest('.filter-form, .row')?.querySelector('form');
            
            if (!form) {
                console.warn('Form not found');
                return;
            }
            
            console.log('Initialized filters for form:', form);
            
            // Prevent form submission completely
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
        console.log('Applying filters...');
        
        // Get all form values
        const formData = new FormData(form);
        const filters = {};
        
        for (const [key, value] of formData.entries()) {
            if (value && value.trim() !== '') {
                filters[key] = value.toLowerCase();
            }
        }
        
        console.log('Filters:', filters);
        
        // Find all filterable rows (tables, lists, cards, etc.)
        const rows = findFilterableRows();
        console.log('Found rows to filter:', rows.length);
        
        let visibleCount = 0;
        
        rows.forEach(function(row) {
            let shouldShow = true;
            
            // Check each filter
            for (const [key, value] of Object.entries(filters)) {
                const rowText = row.textContent.toLowerCase();
                
                // Check if row matches filter
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
        
        // Show message if no results
        showResultCount(visibleCount, rows.length);
        
        // Clear form fields after filtering
        clearFormFields(form);
    }

    function clearFilters(form) {
        console.log('Clearing filters...');
        
        // Clear all form fields
        clearFormFields(form);
        
        // Show all rows
        const rows = findFilterableRows();
        console.log('Showing all rows:', rows.length);
        rows.forEach(function(row) {
            row.style.display = '';
        });
        
        // Remove result message
        removeResultMessage();
    }

    function findFilterableRows() {
        // Find all rows in tables
        const tableRows = Array.from(document.querySelectorAll('table tbody tr'));
        
        // Find all list items
        const listItems = Array.from(document.querySelectorAll('.list-group-item'));
        
        // Find all cards
        const cards = Array.from(document.querySelectorAll('.card, .panel'));
        
        // Combine and return
        return [...tableRows, ...listItems, ...cards].filter(function(el) {
            // Exclude the header row and empty rows
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
            } else if (input.type !== 'hidden' && input.type !== 'submit') {
                input.value = '';
            }
            
            // Trigger change for Select2
            if (input.tagName === 'SELECT' && typeof jQuery !== 'undefined') {
                jQuery(input).trigger('change.select2');
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
