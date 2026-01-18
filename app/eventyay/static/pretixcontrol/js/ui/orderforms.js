// Order forms toggle handlers - adapted from questionToggles.js
(function() {
    'use strict';

    const FIELD_STATES = {
        OPTIONAL: 'optional',
        REQUIRED: 'required',
        DO_NOT_ASK: 'do_not_ask'
    };

    const FIELD_STATES_ARRAY = Object.values(FIELD_STATES);

    document.addEventListener('DOMContentLoaded', () => {
        initOrderFormsToggles();
    });

    function initOrderFormsToggles() {
        // Only run if we are on the order forms page
        if (!document.querySelector('.order-forms-table')) return;

        function updateVisualState(fieldId, value) {
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const toggle = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"]`);
            const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
            
            if (!toggle) return;

            const checkbox = toggle.querySelector('input[type="checkbox"]');

            if (value === FIELD_STATES.DO_NOT_ASK) {
                // Field is inactive
                checkbox.checked = false;
                if (requiredDropdown) {
                    requiredDropdown.disabled = true;
                    requiredDropdown.value = FIELD_STATES.OPTIONAL;
                    const wrapper = requiredDropdown.closest('.required-status-wrapper');
                    if (wrapper) {
                        wrapper.dataset.current = FIELD_STATES.OPTIONAL;
                    }
                }
            } else {
                // Field is active
                checkbox.checked = true;
                if (requiredDropdown) {
                    requiredDropdown.disabled = false;
                    requiredDropdown.value = value;
                    const wrapper = requiredDropdown.closest('.required-status-wrapper');
                    if (wrapper) {
                        wrapper.dataset.current = value;
                    }
                }
            }
        }

        // Initialize from hidden inputs
        document.querySelectorAll('input[type=hidden][id^="id_"]').forEach(input => {
            const fieldId = input.id;
            // Only process fields that have corresponding toggles
            if (document.querySelector(`.toggle-switch[data-field-id="${fieldId}"]`)) {
                updateVisualState(fieldId, input.value);
            }
        });

        // Handle required status dropdown changes
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

        // Handle toggle switch changes (Active/Inactive)
        document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
            input.addEventListener('change', function () {
                const toggle = this.closest('.toggle-switch');
                const fieldId = toggle.dataset.fieldId;
                const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
                const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
                const hiddenInput = document.getElementById(fieldId);

                if (!hiddenInput) return;

                if (this.checked) {
                    // Activate - restore previous state or default to 'optional'
                    let state = hiddenInput.dataset.previousState || (requiredDropdown ? requiredDropdown.value : FIELD_STATES.OPTIONAL);
                    if (!FIELD_STATES_ARRAY.includes(state)) {
                        state = FIELD_STATES.OPTIONAL;
                    }
                    hiddenInput.value = state;
                    updateVisualState(fieldId, state);
                    // Clear stored previous state
                    delete hiddenInput.dataset.previousState;
                } else {
                    // Deactivate - store current state and set to 'do_not_ask'
                    const currentState = hiddenInput.value;
                    if (FIELD_STATES_ARRAY.includes(currentState)) {
                        hiddenInput.dataset.previousState = currentState;
                    }
                    hiddenInput.value = FIELD_STATES.DO_NOT_ASK;
                    updateVisualState(fieldId, FIELD_STATES.DO_NOT_ASK);
                }
            });
        });

        // Handle boolean fields (like order_email_asked_twice) that don't have required/optional
        document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
            const toggle = input.closest('.toggle-switch');
            const fieldId = toggle.dataset.fieldId;
            const hiddenInput = document.getElementById(fieldId);

            // Check if this is a boolean field (value is "True" or "False")
            if (hiddenInput && (hiddenInput.value === 'True' || hiddenInput.value === 'False')) {
                // Initialize checkbox state from hidden input
                input.checked = hiddenInput.value === 'True';

                // Override the change handler for boolean fields
                input.removeEventListener('change', input.onchange);
                input.addEventListener('change', function() {
                    hiddenInput.value = this.checked ? 'True' : 'False';
                });
            }
        });
    }
})();
