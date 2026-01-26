// Question toggle handlers - sync with TalkQuestionRequired model
const REQUIRED_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required',
    AFTER_DEADLINE: 'after_deadline'
};

const REQUIRED_STATES_ARRAY = Object.values(REQUIRED_STATES);

document.addEventListener('DOMContentLoaded', () => {
    initToggles();
    initFormPageToggles();
});

function initToggles() {
    // Required status dropdowns - change event updates state (only those with data-question-id for AJAX)
    document.querySelectorAll('.required-status-dropdown[data-question-id]').forEach(dropdown => {
        dropdown.addEventListener('change', handleRequiredDropdownChange);
    });

    // Binary toggles (active, is_public) - select only those with data-question-id for AJAX
    document.querySelectorAll('.toggle-switch[data-question-id] input').forEach(input => {
        input.addEventListener('change', handleBinaryToggle);
    });
}

/* AJAX Logic for List Page (list.html) */
async function handleRequiredDropdownChange(e) {
    const dropdown = e.target;
    const questionId = dropdown.dataset.questionId;
    const newState = dropdown.value;
    const previousState = dropdown.dataset.current; // Store for error recovery

    // Optimistic UI update
    dropdown.dataset.current = newState;
    
    // Update wrapper data-current for Font Awesome icon color
    const wrapper = dropdown.closest('.required-status-wrapper');
    if (wrapper) {
        wrapper.dataset.current = newState;
    }
    
    dropdown.classList.add('loading');

    try {
        await updateField(questionId, 'question_required', newState);
    } catch (err) {
        // Revert to previous state on error
        dropdown.dataset.current = previousState;
        dropdown.value = previousState;
        if (wrapper) {
            wrapper.dataset.current = previousState;
        }
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

    toggle.classList.add('loading');

    try {
        await updateField(questionId, field, value);
    } catch (err) {
        // Revert checkbox state on error
        input.checked = previousValue;
        showError('Failed to update field. Please try again.');
    } finally {
        toggle.classList.remove('loading');
    }
}

async function updateField(questionId, field, value) {
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    const csrfToken = getCookie('eventyay_csrftoken') || getCookie('csrftoken');

    if (!csrfToken) {
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
        throw new Error(errorMessage);
    }

    const result = await response.json();
    return result;
}

function showError(message) {
    alert(message);
}

/* Local Logic for Form Page (text.html) which uses hidden inputs */
function initFormPageToggles() {
    // Only run if we are on the form page
    if (!document.querySelector('.cfp-option-table')) return;

    function updateVisualState(fieldId, value) {
        const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
        const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
        const toggleInput = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

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
            requiredDropdown.dataset.current = value;
            
            // Update wrapper data-current for Font Awesome icon color
            const wrapper = requiredDropdown.closest('.required-status-wrapper');
            if (wrapper) {
                wrapper.dataset.current = value;
            }
        }
    }

    // Init from hidden inputs
    document.querySelectorAll('input[type=hidden][data-is-question-field="true"]').forEach(input => {
        updateVisualState(input.id, input.value);
    });

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

    document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
        input.addEventListener('change', function () {
            const toggle = this.closest('.toggle-switch');
            const fieldId = toggle.dataset.fieldId;
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
            const hiddenInput = document.getElementById(fieldId);

            if (!hiddenInput || !requiredDropdown) return;

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
                hiddenInput.value = 'do_not_ask';
                updateVisualState(fieldId, 'do_not_ask');
            }
        });
    });
}
