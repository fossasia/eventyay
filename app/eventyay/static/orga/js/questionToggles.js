/**
 * Question toggle handlers
 * Issue #1005: on/off buttons for Required, Active and Public
 */

// State constants - MUST stay in sync with TalkQuestionRequired in base/models/question.py
const REQUIRED_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required',
    AFTER_DEADLINE: 'after_deadline'
};

const REQUIRED_LABELS = {
    [REQUIRED_STATES.OPTIONAL]: 'Optional',
    [REQUIRED_STATES.REQUIRED]: 'Required',
    [REQUIRED_STATES.AFTER_DEADLINE]: 'Deadline'
};

const REQUIRED_STATES_ARRAY = Object.values(REQUIRED_STATES);

document.addEventListener('DOMContentLoaded', () => {
    initToggles();
    initFormPageToggles();
});

function initToggles() {
    // Required status dropdowns - change event updates state
    document.querySelectorAll('.required-status-dropdown:not([data-field-id])').forEach(dropdown => {
        // Set initial data-current attribute based on selected value
        const selectedValue = dropdown.value;
        dropdown.setAttribute('data-current', selectedValue);
        console.log('[Init] Set data-current for dropdown to:', selectedValue);
        
        dropdown.addEventListener('change', handleRequiredDropdownChange);
    });

    // Binary toggles (active, is_public) - select only those without data-field-id (which are for form page)
    document.querySelectorAll('.toggle-switch:not([data-field-id]) input').forEach(input => {
        input.addEventListener('change', handleBinaryToggle);
    });
}

/* AJAX Logic for List Page (list.html) */
async function handleRequiredDropdownChange(e) {
    const dropdown = e.target;
    const questionId = dropdown.dataset.questionId;
    const newState = dropdown.value;
    const previousState = dropdown.dataset.current; // Store for error recovery

    console.log('Changing required state:', {
        questionId,
        previousState,
        newState
    });

    // Optimistic UI update - set data-current for CSS colors
    dropdown.setAttribute('data-current', newState);
    dropdown.classList.add('loading');

    try {
        await updateField(questionId, 'question_required', newState);
    } catch (err) {
        console.error('Required dropdown change failed:', {
            questionId,
            error: err.message,
            stack: err.stack,
            previousState,
            newState
        });
        // Revert to previous state on error
        dropdown.setAttribute('data-current', previousState);
        dropdown.value = previousState;
        showError('Failed to update required status. Please try again.');
    } finally {
        dropdown.classList.remove('loading');
    }
}

async function handleBinaryToggle(e) {
    const input = e.target;
    const toggle = input.closest('.toggle-switch');
    const questionId = toggle.dataset.questionId;
    const field = toggle.dataset.field;
    const value = input.checked;
    const previousValue = !value; // Store for error recovery

    console.log('Toggling binary field:', {
        questionId,
        field,
        value,
        previousValue
    });

    toggle.classList.add('loading');

    try {
        await updateField(questionId, field, value);
    } catch (err) {
        console.error('Toggle failed:', {
            questionId,
            field,
            error: err.message,
            stack: err.stack,
            value,
            previousValue
        });
        // Revert checkbox state on error
        input.checked = previousValue;
        showError('Failed to update field. Please try again.');
    } finally {
        toggle.classList.remove('loading');
    }
}

async function updateField(questionId, field, value) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='))?.split('=')[1];
    
    if (!csrfToken) {
        console.error('CSRF token is missing. Aborting request for question:', questionId);
        alert('Unable to save your changes because a security token is missing or your session has expired. Please reload the page and try again.');
        throw new Error('CSRF token not found. Please refresh the page and try again.');
    }
    
    const response = await fetch(`${questionId}/toggle/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ field, value }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        const errorMessage = errorData.error || `HTTP ${response.status}`;
        console.error('Toggle API error:', {
            status: response.status,
            statusText: response.statusText,
            error: errorMessage,
            field: field,
            value: value,
            questionId: questionId
        });
        throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log('Toggle successful:', result);
    return result;
}

/**
 * Show error message to user
 */
function showError(message) {
    // Try to use existing alert system if available
    const alertContainer = document.querySelector('.alert-container') || document.body;
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.setAttribute('role', 'alert');
    
    const messageText = document.createTextNode(message);
    alert.appendChild(messageText);
    
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');
    alert.appendChild(closeButton);
    
    // Insert at top of container
    alertContainer.insertBefore(alert, alertContainer.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}

/* Local Logic for Form Page (text.html) which uses hidden inputs */
function initFormPageToggles() {
    // Only run if we are on the form page
    if (!document.querySelector('.cfp-option-table')) return;

    // Function to update visual state based on hidden input value
    function updateVisualState(fieldId, value) {
        // Use getElementById for more secure selection
        const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${CSS.escape(fieldId)}"]`);
        const toggleInput = document.querySelector(`.toggle-switch[data-field-id="${CSS.escape(fieldId)}"] input`);

        if (!requiredDropdown || !toggleInput) return;

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
            requiredDropdown.setAttribute('data-current', value);
            console.log('[Form Page] Updated data-current to:', value, 'for field:', fieldId);
        }
    }

    // Init from hidden inputs
    document.querySelectorAll('input[type=hidden][name^="cfp_ask_"]').forEach(input => {
        updateVisualState(input.id, input.value);
    });

    // Handle Required status dropdown change (Form Page)
    document.querySelectorAll('.required-status-dropdown[data-field-id]').forEach(dropdown => {
        dropdown.addEventListener('change', function () {
            const fieldId = this.dataset.fieldId;
            const hiddenInput = document.getElementById(fieldId);
            const checkbox = document.querySelector(`.toggle-switch[data-field-id="${CSS.escape(fieldId)}"] input`);

            if (!checkbox.checked) return; // Can't change if inactive

            const newValue = this.value;
            
            // Update data-current for CSS color
            this.setAttribute('data-current', newValue);
            console.log('[Form Page] Dropdown changed to:', newValue, 'for field:', fieldId);
            
            // Update hidden input
            hiddenInput.value = newValue;
            updateVisualState(fieldId, newValue);
        });
    });
    });

    // Handle Active toggle (Form Page)
    document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
        input.addEventListener('change', function () {
            const toggle = this.closest('.toggle-switch');
            const fieldId = toggle.dataset.fieldId;
            const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${CSS.escape(fieldId)}"]`);
            const hiddenInput = document.getElementById(fieldId);

            if (this.checked) {
                // Activate - restore previous state or default to 'optional'
                // Check if we have a stored previous state
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
                hiddenInput.value = 'do_not_ask';
                updateVisualState(fieldId, 'do_not_ask');
            }
        });
    });
}
