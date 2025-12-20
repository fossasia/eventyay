/**
 * Auto-save CfP form data to sessionStorage to preserve it during browser navigation
 * This ensures data is not lost when users use the browser back button
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

    // Find all form fields using querySelectorAll for reliability
    const textareas = form.querySelectorAll('textarea');
    const inputs = form.querySelectorAll('input:not([type="hidden"]):not([type="submit"])');
    const selects = form.querySelectorAll('select');

    // Process all textareas
    textareas.forEach((textarea) => {
        const name = textarea.name;
        if (name && name !== 'csrfmiddlewaretoken') {
            formData[name] = textarea.value;
        }
    });

    // Process all inputs
    inputs.forEach((input) => {
        const name = input.name;
        const type = input.type;

        if (!name || name === 'csrfmiddlewaretoken' || name === 'action') return;

        if (type === 'checkbox') {
            formData[name] = input.checked;
        } else if (type === 'radio') {
            if (input.checked) {
                formData[name] = input.value;
            }
        } else if (type !== 'file') {
            formData[name] = input.value;
        }
    });

    // Process all selects
    selects.forEach((select) => {
        const name = select.name;
        if (name && name !== 'csrfmiddlewaretoken') {
            if (select.multiple) {
                formData[name] = Array.from(select.selectedOptions).map(opt => opt.value);
            } else {
                formData[name] = select.value;
            }
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

            // Handle NodeList (radio buttons, checkboxes with same name)
            if (elements.length > 1) {
                for (let i = 0; i < elements.length; i++) {
                    const element = elements[i];
                    if (element.type === 'checkbox') {
                        element.checked = value;
                    } else if (element.type === 'radio') {
                        element.checked = (element.value === value);
                    }
                }
            } else {
                const element = elements.length !== undefined ? elements[0] : elements;
                const type = element.type;

                if (type === 'checkbox') {
                    element.checked = value;
                } else if (type === 'radio') {
                    element.checked = (element.value === value);
                } else if (element.tagName === 'SELECT') {
                    if (element.multiple && Array.isArray(value)) {
                        for (let i = 0; i < element.options.length; i++) {
                            element.options[i].selected = value.includes(element.options[i].value);
                        }
                    } else {
                        element.value = value;
                    }
                } else if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
                    // Always restore - sessionStorage takes precedence
                    // If we got this far, the matching logic already determined
                    // this is new data that should be restored
                    element.value = value;
                }
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

