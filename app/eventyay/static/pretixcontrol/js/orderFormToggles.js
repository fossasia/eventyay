/*global $*/

const REQUIRED_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required',
    DO_NOT_ASK: 'do_not_ask'
};

const REQUIRED_STATES_ARRAY = Object.values(REQUIRED_STATES);

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    return parts.length === 2 ? parts.pop().split(';').shift() : null;
}

function getCSRFToken() {
    return getCookie('pretix_csrftoken') || getCookie('csrftoken') || 
           document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || null;
}

async function updateQuestionField(questionId, field, value) {
    const csrfToken = getCSRFToken();
    if (!csrfToken) {
        throw new Error('CSRF token not found');
    }

    const basePath = window.location.pathname.replace(/\/orderforms\/?$/, '');
    const url = `${basePath}/questions/${questionId}/toggle/`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ field, value })
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Server error: ${response.status}`);
    }

    return response;
}

function showFeedback(element, success) {
    const color = success ? '#d4edda' : '#f8d7da';
    const originalBg = element.style.backgroundColor;
    element.style.backgroundColor = color;
    setTimeout(() => {
        element.style.backgroundColor = originalBg;
    }, 500);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOrderFormToggles);
} else {
    initOrderFormToggles();
}

function initOrderFormToggles() {
    if (!document.querySelector('.order-form-option-table')) return;

    function updateVisualState(fieldId, value) {
        const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
        const requiredDropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
        const toggleInput = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

        if (!toggleInput) return;

        if (requiredDropdown) {
            const wrapper = requiredDropdown.closest('.required-status-wrapper');
            
            if (value === REQUIRED_STATES.DO_NOT_ASK) {
                toggleInput.checked = false;
                requiredDropdown.disabled = true;
                wrapper?.classList.add('is-disabled');
            } else {
                toggleInput.checked = true;
                requiredDropdown.disabled = false;
                requiredDropdown.value = value;
                requiredDropdown.dataset.current = value;
                
                if (wrapper) {
                    wrapper.dataset.current = value;
                    wrapper.classList.remove('is-disabled');
                }
            }
        } else {
            toggleInput.checked = (value === 'True' || value === true || value === 'true');
        }
    }

    document.querySelectorAll('input[type=hidden][name^="settings-order_"], input[type=hidden][name^="settings-attendee_"]').forEach(input => {
        updateVisualState(input.id, input.value);
    });

    let currentOpenInfoBox = null;
    document.addEventListener('click', function(e) {
        const toggle = e.target.closest('.info-toggle[data-toggle="info-box"]');
        
        if (toggle) {
            const infoBox = toggle.nextElementSibling;
            if (infoBox?.classList.contains('inline-info-box')) {
                if (currentOpenInfoBox && currentOpenInfoBox !== infoBox) {
                    currentOpenInfoBox.classList.add('d-none');
                }
                infoBox.classList.toggle('d-none');
                currentOpenInfoBox = infoBox.classList.contains('d-none') ? null : infoBox;
            }
            e.stopPropagation();
            return;
        }
        
        if (!e.target.closest('.inline-info-box, .info-toggle-wrapper') && currentOpenInfoBox) {
            currentOpenInfoBox.classList.add('d-none');
            currentOpenInfoBox = null;
        }
    });

    document.querySelectorAll('.question-active-toggle[data-question-id]').forEach(toggle => {
        toggle.addEventListener('change', async function() {
            const questionId = this.dataset.questionId;
            const newValue = this.checked;
            const previousValue = !newValue;
            const container = this.closest('.toggle-switch');

            this.disabled = true;

            try {
                await updateQuestionField(questionId, 'active', newValue);
                showFeedback(container, true);
            } catch (error) {
                console.error('Failed to update active status:', error);
                this.checked = previousValue;
                showFeedback(container, false);
                alert('Failed to update active status. Please try again.');
            } finally {
                this.disabled = false;
            }
        });
    });

    document.querySelectorAll('.question-required-dropdown[data-question-id]').forEach(dropdown => {
        dropdown.addEventListener('change', async function() {
            const questionId = this.dataset.questionId;
            const newValue = this.value === 'required';
            const previousValue = this.dataset.current;
            const wrapper = this.closest('.required-status-wrapper');

            this.dataset.current = this.value;
            if (wrapper) {
                wrapper.dataset.current = this.value;
            }

            this.disabled = true;

            try {
                await updateQuestionField(questionId, 'required', newValue);
                showFeedback(this, true);
            } catch (error) {
                console.error('Failed to update required status:', error);
                this.dataset.current = previousValue;
                this.value = previousValue;
                if (wrapper) {
                    wrapper.dataset.current = previousValue;
                }
                showFeedback(this, false);
                alert('Failed to update required status. Please try again.');
            } finally {
                this.disabled = false;
            }
        });
    });

    document.querySelectorAll('.required-status-dropdown[data-field-id]').forEach(dropdown => {
        dropdown.addEventListener('change', function () {
            const fieldId = this.dataset.fieldId;
            const hiddenInput = document.getElementById(fieldId);
            const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
            const checkbox = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

            if (!hiddenInput || !checkbox || !checkbox.checked) return;

            const newValue = this.value;
            if (!REQUIRED_STATES_ARRAY.includes(newValue)) return;

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

            if (!hiddenInput) return;

            if (!requiredDropdown) {
                hiddenInput.value = this.checked ? 'True' : 'False';
            } else {
                if (this.checked) {
                    let state = hiddenInput.dataset.previousState || requiredDropdown.value;
                    if (!REQUIRED_STATES_ARRAY.includes(state)) {
                        state = REQUIRED_STATES.OPTIONAL;
                    }
                    hiddenInput.value = state;
                    updateVisualState(fieldId, state);
                    delete hiddenInput.dataset.previousState;
                } else {
                    if (hiddenInput.value !== REQUIRED_STATES.DO_NOT_ASK) {
                        hiddenInput.dataset.previousState = hiddenInput.value;
                    }
                    hiddenInput.value = REQUIRED_STATES.DO_NOT_ASK;
                    updateVisualState(fieldId, REQUIRED_STATES.DO_NOT_ASK);
                }
            }
        });
    });
}
