/**
 * Auto-save CfP form data to sessionStorage to preserve it during browser navigation
 * This ensures data is not lost when users use the browser back button
 *
 * Uses the FormData API for reliable form field collection
 */

'use strict';

// Get unique storage key based on the current URL (includes tmpid and step)
function getStorageKey() {
    const path = window.location.pathname;
    return `cfp_form_data_${path}`;
}

// Debounce function to avoid saving too frequently
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Save form data to sessionStorage
function saveFormData() {
    const form = document.getElementById('cfp-submission-form');
    if (!form) return;

    const formData = {};
    const data = new FormData(form);

    // Convert FormData to plain object
    for (const [name, value] of data.entries()) {
        // Skip excluded fields
        if (name === 'csrfmiddlewaretoken' || name === 'action') continue;

        // Skip file inputs - they can't be serialized to sessionStorage
        const element = form.elements[name];
        if (element && element.type === 'file') continue;

        // Handle multiple values for same name (e.g., multi-select)
        if (formData.hasOwnProperty(name)) {
            // Convert to array if not already
            if (!Array.isArray(formData[name])) {
                formData[name] = [formData[name]];
            }
            formData[name].push(value);
        } else {
            formData[name] = value;
        }
    }

    // FormData doesn't include unchecked checkboxes, so we need to add them
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach((checkbox) => {
        if (checkbox.name && checkbox.name !== 'csrfmiddlewaretoken' && !formData.hasOwnProperty(checkbox.name)) {
            formData[checkbox.name] = false;
        } else if (checkbox.name && formData.hasOwnProperty(checkbox.name)) {
            // Checkbox is checked (already in formData from FormData)
            formData[checkbox.name] = true;
        }
    });

    try {
        sessionStorage.setItem(getStorageKey(), JSON.stringify(formData));
    } catch (e) {
        console.warn('Failed to save form data to sessionStorage:', e);
    }
}

// Restore form data from sessionStorage
function restoreFormData() {
    try {
        const savedData = sessionStorage.getItem(getStorageKey());
        if (!savedData) return;

        const formData = JSON.parse(savedData);
        const form = document.getElementById('cfp-submission-form');
        if (!form) return;

        // Check if the saved sessionStorage data matches the current form data
        // If they match exactly, it means we successfully submitted and the server
        // echoed back our data - in this case, clear sessionStorage
        let allFieldsMatch = true;
        let checkedFields = 0;

        for (const [name, savedValue] of Object.entries(formData)) {
            const elements = form.elements[name];
            if (!elements) continue;

            const element = elements.length !== undefined ? elements[0] : elements;
            const currentValue = element.value || '';
            const savedValueStr = String(savedValue || '');

            checkedFields++;
            if (currentValue.trim() !== savedValueStr.trim()) {
                allFieldsMatch = false;
                break;
            }
        }

        // If all saved fields match current values AND we checked some fields,
        // it means the form was successfully submitted - clear sessionStorage
        if (allFieldsMatch && checkedFields > 0) {
            clearFormData();
            return;
        }

        // Otherwise, restore from sessionStorage
        for (const [name, value] of Object.entries(formData)) {
            const elements = form.elements[name];
            if (!elements) continue;

            // Get the actual element(s)
            const element = elements.length !== undefined ? elements[0] : elements;

            if (element.type === 'checkbox') {
                // Handle checkboxes (value is boolean)
                if (elements.length > 1) {
                    // Multiple checkboxes with same name
                    for (let i = 0; i < elements.length; i++) {
                        elements[i].checked = value;
                    }
                } else {
                    element.checked = value;
                }
            } else if (element.type === 'radio') {
                // Handle radio buttons
                for (let i = 0; i < elements.length; i++) {
                    elements[i].checked = (elements[i].value === value);
                }
            } else if (element.tagName === 'SELECT' && element.multiple) {
                // Handle multi-select
                const values = Array.isArray(value) ? value : [value];
                for (let i = 0; i < element.options.length; i++) {
                    element.options[i].selected = values.includes(element.options[i].value);
                }
            } else {
                // Handle text inputs, textareas, single selects
                element.value = value;
            }
        }
    } catch (e) {
        console.warn('Failed to restore form data from sessionStorage:', e);
    }
}

// Clear saved form data (called after successful submission)
function clearFormData() {
    try {
        sessionStorage.removeItem(getStorageKey());
    } catch (e) {
        console.warn('Failed to clear form data from sessionStorage:', e);
    }
}

// Initialize auto-save functionality
function init() {
    const form = document.getElementById('cfp-submission-form');
    if (!form) return;

    // Restore form data on page load
    restoreFormData();

    // Create debounced save function (save 500ms after user stops typing)
    const debouncedSave = debounce(saveFormData, 500);

    // Attach event listeners to form elements
    form.addEventListener('input', debouncedSave);
    form.addEventListener('change', debouncedSave);

    // Save before page unload (browser back button, refresh, close tab, etc.)
    // This ensures data is preserved even when using browser navigation
    window.addEventListener('beforeunload', saveFormData);

    // Note: We don't clear sessionStorage on form submit because:
    // 1. We can't reliably detect if submission succeeded (might have validation errors)
    // 2. The restore logic already handles this by clearing sessionStorage when
    //    it detects the form has server data (successful previous submission)
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

