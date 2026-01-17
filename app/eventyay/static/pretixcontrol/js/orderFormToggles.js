// Order Form toggle and dropdown handlers
// Adapted from orga/js/questionToggles.js for pretixcontrol

const REQUIRED_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required',
    AFTER_DEADLINE: 'after_deadline'
};

const REQUIRED_STATES_ARRAY = Object.values(REQUIRED_STATES);

document.addEventListener('DOMContentLoaded', () => {
    initOrderFormToggles();
});

function initOrderFormToggles() {
    // Only run if we are on the order forms page
    if (!document.querySelector('.order-form-option-table')) return;

    function updateVisualState(fieldId, value) {
        const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
        const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
        const toggleInput = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

        if (!toggleInput) return;

        // Handle fields with required dropdown (asked_required pattern)
        if (requiredDropdown) {
            if (value === 'do_not_ask') {
                toggleInput.checked = false;
                requiredDropdown.disabled = true;
                requiredDropdown.style.opacity = '0.5';
            } else {
                toggleInput.checked = true;
                requiredDropdown.disabled = false;
                requiredDropdown.style.opacity = '1';

                // Update dropdown value and data-current attribute for color
                requiredDropdown.value = value;
                requiredDropdown.dataset.current = value;
                
                // Update wrapper data-current for Font Awesome icon color
                const wrapper = requiredDropdown.closest('.required-status-wrapper');
                if (wrapper) {
                    wrapper.dataset.current = value;
                }
            }
        } else {
            // Handle boolean fields without required dropdown
            toggleInput.checked = (value === 'True' || value === true || value === 'true');
        }
    }

    // Init from hidden inputs for order form fields (settings-order_*, settings-attendee_*)
    document.querySelectorAll('input[type=hidden][name^="settings-order_"], input[type=hidden][name^="settings-attendee_"]').forEach(input => {
        updateVisualState(input.id, input.value);
    });

    // Handle required dropdown changes
    document.querySelectorAll('.required-status-dropdown[data-field-id]').forEach(dropdown => {
        dropdown.addEventListener('change', function () {
            const fieldId = this.dataset.fieldId;
            const hiddenInput = document.getElementById(fieldId);
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const checkbox = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

            if (!hiddenInput || !checkbox.checked) {
                return; // Can't change if inactive
            }

            const newValue = this.value;

            // Update hidden input
            hiddenInput.value = newValue;
            updateVisualState(fieldId, newValue);
        });
    });

    // Handle toggle switch changes
    document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
        input.addEventListener('change', function () {
            const toggle = this.closest('.toggle-switch');
            const fieldId = toggle.dataset.fieldId;
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
            const hiddenInput = document.getElementById(fieldId);

            if (!hiddenInput) return;

            // Check if this is a boolean field (no dropdown) or asked_required field
            if (!requiredDropdown) {
                // Boolean field - just toggle True/False
                hiddenInput.value = this.checked ? 'True' : 'False';
            } else {
                // asked_required field
                if (this.checked) {
                    // Activate - restore previous state or default to 'optional'
                    let state = (hiddenInput.dataset && hiddenInput.dataset.previousState) || requiredDropdown.value;
                    if (!REQUIRED_STATES_ARRAY.includes(state)) {
                        state = REQUIRED_STATES.OPTIONAL;
                    }
                    hiddenInput.value = state;
                    updateVisualState(fieldId, state);
                    // Clear stored previous state
                    if (hiddenInput.dataset) {
                        delete hiddenInput.dataset.previousState;
                    }
                } else {
                    // Deactivate - store current state before deactivating
                    if (hiddenInput.value !== 'do_not_ask') {
                        if (hiddenInput.dataset) {
                            hiddenInput.dataset.previousState = hiddenInput.value;
                        }
                    }
                    hiddenInput.value = 'do_not_ask';
                    updateVisualState(fieldId, 'do_not_ask');
                }
            }
        });
    });
}
