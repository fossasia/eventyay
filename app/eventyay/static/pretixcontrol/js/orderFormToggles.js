// Order Form toggle and dropdown handlers
// Adapted from orga/js/questionToggles.js for pretixcontrol

const REQUIRED_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required'
};

const REQUIRED_STATES_ARRAY = Object.values(REQUIRED_STATES);

// Helper function to get cookie value
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initOrderFormToggles();
    });
} else {
    initOrderFormToggles();
}

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
            const wrapper = requiredDropdown.closest('.required-status-wrapper');
            
            if (value === 'do_not_ask') {
                toggleInput.checked = false;
                requiredDropdown.disabled = true;
                
                // Add .is-disabled class for interaction state
                // Do NOT modify data-current (semantic state must persist)
                if (wrapper) {
                    wrapper.classList.add('is-disabled');
                }
            } else {
                toggleInput.checked = true;
                requiredDropdown.disabled = false;

                // Update dropdown value and data-current attribute for semantic state
                requiredDropdown.value = value;
                requiredDropdown.dataset.current = value;
                
                // Update wrapper data-current for semantic color
                if (wrapper) {
                    wrapper.dataset.current = value;
                    wrapper.classList.remove('is-disabled');
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

    // Handle info-toggle click for info boxes (CSP-compliant)
    let currentOpenInfoBox = null;
    
    // Use event delegation for efficient event handling
    document.addEventListener('click', function(e) {
        const toggle = e.target.closest('.info-toggle[data-toggle="info-box"]');
        
        // Handle info-toggle click
        if (toggle) {
            const infoBox = toggle.nextElementSibling;
            if (infoBox?.classList.contains('inline-info-box')) {
                // Close any other open info boxes
                if (currentOpenInfoBox && currentOpenInfoBox !== infoBox) {
                    currentOpenInfoBox.classList.add('d-none');
                }
                
                // Toggle current info box
                infoBox.classList.toggle('d-none');
                
                // Update reference to currently open info box
                currentOpenInfoBox = infoBox.classList.contains('d-none') ? null : infoBox;
            }
            e.stopPropagation();
            return;
        }
        
        // Close info box when clicking outside (check related elements)
        if (e.target.closest('.inline-info-box, .info-toggle-wrapper')) {
            return;
        }
        
        // Close any open info boxes
        if (currentOpenInfoBox) {
            currentOpenInfoBox.classList.add('d-none');
            currentOpenInfoBox = null;
        }
    });

    // Handle custom field required dropdown changes (AJAX update)
    document.querySelectorAll('.question-required-dropdown[data-question-id]').forEach(dropdown => {
        dropdown.addEventListener('change', async function() {
            const questionId = this.dataset.questionId;
            const fieldName = this.getAttribute('aria-label') || 'this field';
            const newValue = this.value === 'required'; // Convert to boolean
            const previousValue = this.dataset.current;
            const wrapper = this.closest('.required-status-wrapper');
            
            // Optimistic UI update
            this.dataset.current = this.value;
            if (wrapper) {
                wrapper.dataset.current = this.value;
            }
            
            // Add loading state
            this.disabled = true;
            this.classList.add('loading');
            
            try {
                // Get CSRF token
                const csrfToken = getCookie('pretix_csrftoken') || getCookie('csrftoken');
                if (!csrfToken) {
                    throw new Error('CSRF token not found');
                }
                
                // Build URL for toggle endpoint
                const baseUrl = `${window.location.pathname.replace(/\/orderforms\/?$/, '')}`;
                const toggleUrl = `${baseUrl}/questions/${questionId}/toggle/`;
                
                // Send AJAX request
                const response = await fetch(toggleUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({
                        field: 'required',
                        value: newValue
                    })
                });
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
                    throw new Error(errorData.error || `HTTP ${response.status}`);
                }
                
                // Success - show brief feedback
                const originalBg = this.style.backgroundColor;
                this.style.backgroundColor = '#d4edda';
                setTimeout(() => {
                    this.style.backgroundColor = originalBg;
                }, 500);
                
            } catch (error) {
                // Revert on error
                console.error('Failed to update required status', {
                    questionId,
                    fieldName,
                    error,
                });
                this.dataset.current = previousValue;
                this.value = previousValue;
                if (wrapper) {
                    wrapper.dataset.current = previousValue;
                }
                alert(`Failed to update required status for ${fieldName}. Please try again or refresh the page.`);
            } finally {
                this.disabled = false;
                this.classList.remove('loading');
            }
        });
    });

    // Handle required dropdown changes
    document.querySelectorAll('.required-status-dropdown[data-field-id]').forEach(dropdown => {
        dropdown.addEventListener('change', function () {
            const fieldId = this.dataset.fieldId;
            const hiddenInput = document.getElementById(fieldId);
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const checkbox = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

            if (!hiddenInput || !checkbox || !checkbox.checked) {
                return; // Can't change if inactive
            }

            const newValue = this.value;

            // Validate dropdown value before assigning
            if (!REQUIRED_STATES_ARRAY.includes(newValue)) {
                return;
            }

            // Update hidden input
            hiddenInput.value = newValue;
            updateVisualState(fieldId, newValue);
        });
    });

    // Handle toggle switch changes
    document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
        input.addEventListener('change', async function () {
            const toggle = this.closest('.toggle-switch');
            const fieldId = toggle.dataset.fieldId;
            const questionId = toggle.dataset.questionId;
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
            const hiddenInput = document.getElementById(fieldId);

            if (!hiddenInput) return;

            // Check if this is a custom question (has data-question-id)
            if (questionId) {
                const newActiveState = this.checked;
                const previousChecked = !newActiveState;
                
                this.checked = newActiveState;
                
                toggle.classList.add('loading');
                this.disabled = true;
                
                try {
                    const csrfToken = getCookie('pretix_csrftoken') || getCookie('csrftoken');
                    if (!csrfToken) {
                        throw new Error('CSRF token not found');
                    }

                    const baseUrl = `${window.location.pathname.replace(/\/orderforms\/?$/, '')}`;
                    const toggleUrl = `${baseUrl}/questions/${questionId}/toggle/`;
                    
                    const response = await fetch(toggleUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        },
                        body: JSON.stringify({
                            field: 'active',
                            value: newActiveState
                        })
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
                        throw new Error(errorData.error || `HTTP ${response.status}`);
                    }
                    
                    const result = await response.json();
                    
                    const currentValue = hiddenInput.value;
                    
                    if (newActiveState) {
                        let state = hiddenInput.dataset.previousState || 'optional';
                        if (!REQUIRED_STATES_ARRAY.includes(state)) {
                            state = REQUIRED_STATES.OPTIONAL;
                        }
                        hiddenInput.value = state;
                        const questionRequiredDropdown = document.querySelector(`.question-required-dropdown[data-question-id="${questionId}"]`);
                        if (questionRequiredDropdown) {
                            const wrapper = questionRequiredDropdown.closest('.required-status-wrapper');
                            questionRequiredDropdown.disabled = false;
                            if (wrapper) {
                                wrapper.classList.remove('is-disabled');
                            }
                        }
                        delete hiddenInput.dataset.previousState;
                    } else {
                        if (currentValue !== 'do_not_ask') {
                            hiddenInput.dataset.previousState = currentValue;
                        }
                        hiddenInput.value = 'do_not_ask';
                        const questionRequiredDropdown = document.querySelector(`.question-required-dropdown[data-question-id="${questionId}"]`);
                        if (questionRequiredDropdown) {
                            const wrapper = questionRequiredDropdown.closest('.required-status-wrapper');
                            questionRequiredDropdown.disabled = true;
                            if (wrapper) {
                                wrapper.classList.add('is-disabled');
                            }
                        }
                    }
                    const originalBg = toggle.style.backgroundColor;
                    toggle.style.backgroundColor = '#d4edda';
                    setTimeout(() => {
                        toggle.style.backgroundColor = originalBg;
                    }, 500);
                    
                } catch (error) {
                    console.error('Failed to toggle question active state', {
                        questionId,
                        error,
                    });
                    this.checked = previousChecked;
                    alert(`Failed to ${newActiveState ? 'activate' : 'deactivate'} the custom question. Please try again or refresh the page.`);
                } finally {
                    toggle.classList.remove('loading');
                    this.disabled = false;
                }
                return;
            }
            // Check if this is a boolean field (no dropdown) or asked_required field
            if (!requiredDropdown) {
                // Boolean field - just toggle True/False
                hiddenInput.value = this.checked ? 'True' : 'False';
            } else {
                // asked_required field
                if (this.checked) {
                    // Activate - restore previous state or default to 'optional'
                    let state = hiddenInput.dataset.previousState || requiredDropdown.value;
                    if (!REQUIRED_STATES_ARRAY.includes(state)) {
                        state = REQUIRED_STATES.OPTIONAL;
                    }
                    hiddenInput.value = state;
                    updateVisualState(fieldId, state);
                    // Clear stored previous state
                    delete hiddenInput.dataset.previousState;
                } else {
                    // Deactivate - store current state before deactivating
                    if (hiddenInput.value !== 'do_not_ask') {
                        hiddenInput.dataset.previousState = hiddenInput.value;
                    }
                    // Set hidden input to do_not_ask for backend and update visuals accordingly
                    hiddenInput.value = 'do_not_ask';
                    updateVisualState(fieldId, 'do_not_ask');
                }
            }
        });
    });
}
