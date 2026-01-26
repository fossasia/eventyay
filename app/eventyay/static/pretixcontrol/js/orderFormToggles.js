// Order Form toggle and dropdown handlers
// Adapted from orga/js/questionToggles.js for pretixcontrol

const REQUIRED_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required'
};

const REQUIRED_STATES_ARRAY = Object.values(REQUIRED_STATES);

/**
 * Get cookie value by name
 * @param {string} name - Cookie name
 * @returns {string|null} Cookie value or null if not found
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    return parts.length === 2 ? parts.pop().split(';').shift() : null;
}

/**
 * Get CSRF token from cookie or hidden input
 * @returns {string|null} CSRF token or null if not found
 */
function getCSRFToken() {
    // Try cookie first
    const token = getCookie('pretix_csrftoken') || getCookie('csrftoken');
    if (token) return token;
    
    // Fallback to hidden input field
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfInput?.value ?? null;
}

/**
 * Send AJAX request to toggle endpoint with CSRF protection
 * @param {string} questionId - Question ID
 * @param {string} field - Field name ('active' or 'required')
 * @param {boolean} value - New value
 * @returns {Promise<Response>} Fetch response
 * @throws {Error} When CSRF token not found or request fails
 */
async function updateQuestionField(questionId, field, value) {
    const csrfToken = getCSRFToken();
    if (!csrfToken) {
        throw new Error('CSRF token not found');
    }
    
    const baseUrl = window.location.pathname.replace(/\/orderforms\/?$/, '');
    const toggleUrl = `${baseUrl}/questions/${questionId}/toggle/`;
    
    const response = await fetch(toggleUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ field, value })
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({
            error: `HTTP ${response.status} ${response.statusText || 'Unknown error'}`
        }));
        throw new Error(errorData.error || `HTTP ${response.status} ${response.statusText}`);
    }
    
    return response;
}

/**
 * Show visual success feedback by briefly flashing background color
 * @param {HTMLElement} element - Element to flash
 * @param {string} color - Background color for flash (default: green)
 * @param {number} duration - Duration in ms (default: 500)
 */
function showSuccessFeedback(element, color = '#d4edda', duration = 500) {
    const originalBg = element.style.backgroundColor;
    element.style.backgroundColor = color;
    setTimeout(() => {
        element.style.backgroundColor = originalBg;
    }, duration);
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
    
    // Init disabled state for custom question dropdowns based on active toggle
    document.querySelectorAll('.question-active-toggle[data-question-id]').forEach(toggle => {
        const row = toggle.closest('tr');
        const requiredDropdown = row?.querySelector('.question-required-dropdown');
        const wrapper = requiredDropdown?.closest('.required-status-wrapper');
        
        if (requiredDropdown) {
            if (toggle.checked) {
                requiredDropdown.disabled = false;
                wrapper?.classList.remove('is-disabled');
            } else {
                requiredDropdown.disabled = true;
                wrapper?.classList.add('is-disabled');
            }
        }
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

    // Handle custom question active toggle changes (AJAX update)
    document.querySelectorAll('.question-active-toggle[data-question-id]').forEach(toggle => {
        toggle.addEventListener('change', async function() {
            const questionId = this.dataset.questionId;
            const newValue = this.checked;
            const previousValue = !newValue;
            const toggleSwitch = this.closest('.toggle-switch');
            
            // Find the required dropdown for this question
            const row = this.closest('tr');
            const requiredDropdown = row?.querySelector('.question-required-dropdown');
            const wrapper = requiredDropdown?.closest('.required-status-wrapper');
            
            // Add loading state
            this.disabled = true;
            toggleSwitch.classList.add('loading');
            
            try {
                await updateQuestionField(questionId, 'active', newValue);
                
                // Update dropdown disabled state based on active toggle
                if (requiredDropdown) {
                    if (newValue) {
                        requiredDropdown.disabled = false;
                        wrapper?.classList.remove('is-disabled');
                    } else {
                        requiredDropdown.disabled = true;
                        wrapper?.classList.add('is-disabled');
                    }
                }
                
                // Remove focus to prevent green border
                this.blur();
            } catch (error) {
                console.error('Failed to update active status', { questionId, error });
                this.checked = previousValue;
                alert('Failed to update active status. Please try again or refresh the page.');
            } finally {
                this.disabled = false;
                toggleSwitch.classList.remove('loading');
            }
        });
    });

    // Handle custom question required dropdown changes (AJAX update)
    document.querySelectorAll('.question-required-dropdown[data-question-id]').forEach(dropdown => {
        dropdown.addEventListener('change', async function() {
            const questionId = this.dataset.questionId;
            const newValue = this.value === 'required';
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
                await updateQuestionField(questionId, 'required', newValue);
                showSuccessFeedback(this);
            } catch (error) {
                console.error('Failed to update required status', { questionId, error });
                // Revert on error
                this.dataset.current = previousValue;
                this.value = previousValue;
                if (wrapper) {
                    wrapper.dataset.current = previousValue;
                }
                alert('Failed to update required status. Please try again or refresh the page.');
            } finally {
                this.disabled = false;
                this.classList.remove('loading');
            }
        });
    });
}
