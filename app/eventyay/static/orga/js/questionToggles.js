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
    // Required status buttons - cycle through states on click
    document.querySelectorAll('.required-status:not([data-field-id])').forEach(btn => {
        btn.addEventListener('click', handleRequiredClick);
        // Add keyboard accessibility
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleRequiredClick(e);
            }
        });
    });

    // Binary toggles (active, is_public) - select only those without data-field-id (which are for form page)
    document.querySelectorAll('.toggle-switch:not([data-field-id]) input').forEach(input => {
        input.addEventListener('change', handleBinaryToggle);
    });
}

/* AJAX Logic for List Page (list.html) */
async function handleRequiredClick(e) {
    const btn = e.target.closest('.required-status');
    const questionId = btn.dataset.questionId;
    const currentState = btn.dataset.state;
    const previousState = currentState; // Store for error recovery

    // Cycle to next state
    const currentIdx = REQUIRED_STATES_ARRAY.indexOf(currentState);
    const nextState = REQUIRED_STATES_ARRAY[(currentIdx + 1) % REQUIRED_STATES_ARRAY.length];

    // Optimistic UI update
    btn.dataset.state = nextState;
    btn.textContent = REQUIRED_LABELS[nextState];
    btn.classList.add('loading');

    try {
        await updateField(questionId, 'question_required', nextState);
    } catch (err) {
        console.error('Required toggle failed:', err);
        // Revert to previous state on error
        btn.dataset.state = previousState;
        btn.textContent = REQUIRED_LABELS[previousState];
        showError('Failed to update required status. Please try again.');
    } finally {
        btn.classList.remove('loading');
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
        console.error('Toggle failed:', err);
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
        throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    return response.json();
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
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
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
        const requiredBtn = document.querySelector(`.required-status[data-field-id="${CSS.escape(fieldId)}"]`);
        const toggleInput = document.querySelector(`.toggle-switch[data-field-id="${CSS.escape(fieldId)}"] input`);

        if (!requiredBtn || !toggleInput) return;

        if (value === 'do_not_ask') {
            toggleInput.checked = false;
            requiredBtn.style.opacity = '0.5';
            requiredBtn.style.pointerEvents = 'none';
            requiredBtn.setAttribute('aria-disabled', 'true');
        } else {
            toggleInput.checked = true;
            requiredBtn.style.opacity = '1';
            requiredBtn.style.pointerEvents = 'auto';
            requiredBtn.removeAttribute('aria-disabled');

            // Handle all three states: optional, required, after_deadline
            const state = value;
            requiredBtn.dataset.state = state;
            
            // Set button text based on state
            if (state === REQUIRED_STATES.REQUIRED) {
                requiredBtn.textContent = 'Required';
            } else if (state === REQUIRED_STATES.AFTER_DEADLINE) {
                requiredBtn.textContent = 'Deadline';
            } else {
                requiredBtn.textContent = 'Optional';
            }
        }
    }

    // Init from hidden inputs
    document.querySelectorAll('input[type=hidden][name^="cfp_ask_"]').forEach(input => {
        updateVisualState(input.id, input.value);
    });

    // Handle Required status click (Form Page)
    document.querySelectorAll('.required-status[data-field-id]').forEach(btn => {
        btn.addEventListener('click', function () {
            if (this.getAttribute('aria-disabled') === 'true') return;
            
            const fieldId = this.dataset.fieldId;
            const hiddenInput = document.getElementById(fieldId);
            const checkbox = document.querySelector(`.toggle-switch[data-field-id="${CSS.escape(fieldId)}"] input`);

            if (!checkbox.checked) return; // Can't toggle if inactive

            const currentState = this.dataset.state;
            
            // Cycle through all three states: optional → required → after_deadline → optional
            const currentIdx = REQUIRED_STATES_ARRAY.indexOf(currentState);
            const nextState = REQUIRED_STATES_ARRAY[(currentIdx + 1) % REQUIRED_STATES_ARRAY.length];

            // Update hidden input
            hiddenInput.value = nextState;
            updateVisualState(fieldId, nextState);
        });
        
        // Add keyboard accessibility
        btn.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });

    // Handle Active toggle (Form Page)
    document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
        input.addEventListener('change', function () {
            const toggle = this.closest('.toggle-switch');
            const fieldId = toggle.dataset.fieldId;
            const requiredBtn = document.querySelector(`.required-status[data-field-id="${CSS.escape(fieldId)}"]`);
            const hiddenInput = document.getElementById(fieldId);

            if (this.checked) {
                // Activate - restore previous state or default to 'optional'
                // Check if we have a stored previous state
                let state = hiddenInput.dataset.previousState || requiredBtn.dataset.state;
                if (state !== REQUIRED_STATES.REQUIRED && state !== REQUIRED_STATES.OPTIONAL) {
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
