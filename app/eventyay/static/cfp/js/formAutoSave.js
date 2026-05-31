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

function getFieldElements(form, name) {
    const elements = form.elements[name];
    if (!elements) return [];
    if (typeof elements.length === 'number' && !elements.tagName) {
        return Array.from(elements);
    }
    return [elements];
}

function getFieldValue(form, name) {
    const elements = getFieldElements(form, name);
    if (!elements.length) return undefined;

    const [element] = elements;

    if (element.type === 'checkbox') {
        if (elements.length > 1) {
            return elements.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
        }
        return element.checked;
    }

    if (element.type === 'radio') {
        const checkedElement = elements.find((radio) => radio.checked);
        return checkedElement ? checkedElement.value : '';
    }

    if (element.tagName === 'SELECT' && element.multiple) {
        return Array.from(element.options).filter((option) => option.selected).map((option) => option.value);
    }

    return element.value ?? '';
}

function normalizeFieldValue(value) {
    if (Array.isArray(value)) {
        return value.map((item) => String(item).trim()).sort();
    }
    if (typeof value === 'boolean') {
        return value;
    }
    if (value == null) {
        return '';
    }
    return String(value).trim();
}

function fieldValuesMatch(currentValue, savedValue) {
    const normalizedCurrent = normalizeFieldValue(currentValue);
    const normalizedSaved = normalizeFieldValue(savedValue);

    if (Array.isArray(normalizedCurrent) || Array.isArray(normalizedSaved)) {
        const currentArray = Array.isArray(normalizedCurrent) ? normalizedCurrent : [normalizedCurrent];
        const savedArray = Array.isArray(normalizedSaved) ? normalizedSaved : [normalizedSaved];
        if (currentArray.length !== savedArray.length) {
            return false;
        }
        return currentArray.every((value, index) => value === savedArray[index]);
    }

    return normalizedCurrent === normalizedSaved;
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

    // FormData doesn't include unchecked checkboxes. For single checkboxes we
    // store a boolean, and for checkbox groups we store the selected values.
    const checkboxNames = new Set();
    form.querySelectorAll('input[type="checkbox"][name]').forEach((checkbox) => {
        if (checkbox.name && checkbox.name !== 'csrfmiddlewaretoken' && checkbox.name !== 'action') {
            checkboxNames.add(checkbox.name);
        }
    });
    checkboxNames.forEach((name) => {
        formData[name] = getFieldValue(form, name);
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
            const currentValue = getFieldValue(form, name);
            if (currentValue === undefined) continue;
            checkedFields++;
            if (!fieldValuesMatch(currentValue, savedValue)) {
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
            const elements = getFieldElements(form, name);
            if (!elements.length) continue;

            const [element] = elements;

            if (element.type === 'checkbox') {
                if (elements.length > 1) {
                    const selectedValues = Array.isArray(value)
                        ? value.map((entry) => String(entry))
                        : value
                            ? [String(value)]
                            : [];
                    elements.forEach((checkbox) => {
                        checkbox.checked = selectedValues.includes(checkbox.value);
                    });
                } else {
                    element.checked = Boolean(value);
                }
            } else if (element.type === 'radio') {
                elements.forEach((radio) => {
                    radio.checked = (radio.value === value);
                });
            } else if (element.tagName === 'SELECT' && element.multiple) {
                const values = Array.isArray(value) ? value : [value];
                Array.from(element.options).forEach((option) => {
                    option.selected = values.includes(option.value);
                });
            } else {
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
