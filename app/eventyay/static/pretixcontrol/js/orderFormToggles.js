/**
 * Order Form Toggle Handlers
 */

const FIELD_STATES = {
    OPTIONAL: 'optional',
    REQUIRED: 'required',
    DO_NOT_ASK: 'do_not_ask'
};

const VALID_STATES = Object.values(FIELD_STATES);

class CSRFTokenManager {
    static #cachedToken = null;

    static getToken() {
        if (this.#cachedToken) {
            return this.#cachedToken;
        }

        const cookieNames = ['pretix_csrftoken', 'csrftoken', 'eventyay_csrftoken'];
        for (const name of cookieNames) {
            const token = this.#getCookieValue(name);
            if (token) {
                this.#cachedToken = token;
                return token;
            }
        }

        const hiddenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (hiddenInput?.value) {
            this.#cachedToken = hiddenInput.value;
            return hiddenInput.value;
        }

        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag?.content) {
            this.#cachedToken = metaTag.content;
            return metaTag.content;
        }

        return null;
    }

    static #getCookieValue(name) {
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [key, value] = cookie.trim().split('=');
            if (key === name) {
                return decodeURIComponent(value);
            }
        }
        return null;
    }

    static clearCache() {
        this.#cachedToken = null;
    }
}

class QuestionAPI {
    static async updateField(questionId, field, value, options = {}) {
        const { retries = 1, timeout = 10000 } = options;
        
        let lastError;
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                return await this.#makeRequest(questionId, field, value, timeout);
            } catch (error) {
                lastError = error;
                if (attempt < retries) {
                    await this.#delay(Math.min(1000 * Math.pow(2, attempt), 5000));
                }
            }
        }
        
        throw lastError;
    }

    static async #makeRequest(questionId, field, value, timeout) {
        const csrfToken = CSRFTokenManager.getToken();
        if (!csrfToken) {
            throw new Error('CSRF token not found. Please refresh the page.');
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const url = this.#buildURL(questionId);
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ field, value }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(
                    errorData.error || 
                    `Server error: ${response.status} ${response.statusText}`
                );
            }

            return await response.json().catch(() => ({}));
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('Request timeout. Please try again.');
            }
            throw error;
        }
    }

    static #buildURL(questionId) {
        const basePath = window.location.pathname.replace(/\/orderforms\/?$/, '');
        return `${basePath}/questions/${questionId}/toggle/`;
    }

    static #delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

class UIFeedback {
    static showSuccess(element, duration = 600) {
        const originalBg = element.style.backgroundColor;
        element.style.transition = 'background-color 0.3s ease';
        element.style.backgroundColor = '#d4edda';
        
        setTimeout(() => {
            element.style.backgroundColor = originalBg;
            setTimeout(() => {
                element.style.transition = '';
            }, 300);
        }, duration);
    }

    static showError(element, duration = 1000) {
        const originalBg = element.style.backgroundColor;
        element.style.transition = 'background-color 0.3s ease';
        element.style.backgroundColor = '#f8d7da';
        
        setTimeout(() => {
            element.style.backgroundColor = originalBg;
            setTimeout(() => {
                element.style.transition = '';
            }, 300);
        }, duration);
    }

    static setLoading(element, isLoading) {
        if (isLoading) {
            element.classList.add('loading');
            element.style.opacity = '0.6';
            element.style.pointerEvents = 'none';
        } else {
            element.classList.remove('loading');
            element.style.opacity = '';
            element.style.pointerEvents = '';
        }
    }
}

class QuestionToggleHandler {
    constructor() {
        this.activeToggles = new Map();
        this.requiredDropdowns = new Map();
    }

    initialize() {
        this.#initActiveToggles();
        this.#initRequiredDropdowns();
    }

    #initActiveToggles() {
        document.querySelectorAll('.question-active-toggle[data-question-id]').forEach(toggle => {
            const questionId = toggle.dataset.questionId;
            this.activeToggles.set(questionId, toggle);

            toggle.addEventListener('change', async (e) => {
                await this.#handleActiveToggle(e.target);
            });
        });
    }

    #initRequiredDropdowns() {
        document.querySelectorAll('.question-required-dropdown[data-question-id]').forEach(dropdown => {
            const questionId = dropdown.dataset.questionId;
            this.requiredDropdowns.set(questionId, dropdown);

            dropdown.addEventListener('change', async (e) => {
                await this.#handleRequiredChange(e.target);
            });
        });
    }

    async #handleActiveToggle(toggle) {
        const questionId = toggle.dataset.questionId;
        const newValue = toggle.checked;
        const previousValue = !newValue;
        const container = toggle.closest('.toggle-switch');

        toggle.disabled = true;
        UIFeedback.setLoading(container, true);

        try {
            await QuestionAPI.updateField(questionId, 'active', newValue, { retries: 2 });
            UIFeedback.showSuccess(container);
        } catch (error) {
            console.error('[QuestionToggle] Failed to update active status:', {
                questionId,
                error: error.message
            });
            
            toggle.checked = previousValue;
            UIFeedback.showError(container);
            
            this.#showErrorNotification(
                'Failed to update active status',
                error.message
            );
        } finally {
            toggle.disabled = false;
            UIFeedback.setLoading(container, false);
        }
    }

    async #handleRequiredChange(dropdown) {
        const questionId = dropdown.dataset.questionId;
        const newValue = dropdown.value === 'required';
        const previousValue = dropdown.dataset.current;
        const wrapper = dropdown.closest('.required-status-wrapper');

        dropdown.dataset.current = dropdown.value;
        if (wrapper) {
            wrapper.dataset.current = dropdown.value;
        }

        dropdown.disabled = true;
        UIFeedback.setLoading(dropdown, true);

        try {
            await QuestionAPI.updateField(questionId, 'required', newValue, { retries: 2 });
            UIFeedback.showSuccess(dropdown);
        } catch (error) {
            console.error('[QuestionToggle] Failed to update required status:', {
                questionId,
                error: error.message
            });

            dropdown.dataset.current = previousValue;
            dropdown.value = previousValue;
            if (wrapper) {
                wrapper.dataset.current = previousValue;
            }
            
            UIFeedback.showError(dropdown);
            this.#showErrorNotification(
                'Failed to update required status',
                error.message
            );
        } finally {
            dropdown.disabled = false;
            UIFeedback.setLoading(dropdown, false);
        }
    }

    #showErrorNotification(title, message) {
        alert(`${title}\n\n${message}\n\nPlease try again or refresh the page.`);
    }
}

class SystemFieldHandler {
    initialize() {
        this.#initFromHiddenInputs();
        this.#attachToggleListeners();
        this.#attachDropdownListeners();
        this.#initInfoBoxes();
    }

    #initFromHiddenInputs() {
        const hiddenInputs = document.querySelectorAll(
            'input[type=hidden][name^="settings-order_"], ' +
            'input[type=hidden][name^="settings-attendee_"]'
        );

        hiddenInputs.forEach(input => {
            this.#updateVisualState(input.id, input.value);
        });
    }

    #updateVisualState(fieldId, value) {
        const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
        const dropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
        const toggle = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

        if (!toggle) return;

        if (dropdown) {
            const wrapper = dropdown.closest('.required-status-wrapper');
            
            if (value === FIELD_STATES.DO_NOT_ASK) {
                toggle.checked = false;
                dropdown.disabled = true;
                wrapper?.classList.add('is-disabled');
            } else {
                toggle.checked = true;
                dropdown.disabled = false;
                dropdown.value = value;
                dropdown.dataset.current = value;
                
                if (wrapper) {
                    wrapper.dataset.current = value;
                    wrapper.classList.remove('is-disabled');
                }
            }
        } else {
            toggle.checked = (value === 'True' || value === true || value === 'true');
        }
    }

    #attachToggleListeners() {
        document.querySelectorAll('.toggle-switch[data-field-id] input').forEach(input => {
            input.addEventListener('change', (e) => {
                this.#handleToggleChange(e.target);
            });
        });
    }

    #attachDropdownListeners() {
        document.querySelectorAll('.required-status-dropdown[data-field-id]').forEach(dropdown => {
            dropdown.addEventListener('change', (e) => {
                this.#handleDropdownChange(e.target);
            });
        });
    }

    #handleToggleChange(toggle) {
        const container = toggle.closest('.toggle-switch');
        const fieldId = container.dataset.fieldId;
        const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
        const dropdown = document.querySelector(`.required-status-dropdown[data-field-id="${escapedId}"]`);
        const hiddenInput = document.getElementById(fieldId);

        if (!hiddenInput) return;

        if (!dropdown) {
            hiddenInput.value = toggle.checked ? 'True' : 'False';
        } else {
            if (toggle.checked) {
                let state = hiddenInput.dataset.previousState || dropdown.value;
                if (!VALID_STATES.includes(state)) {
                    state = FIELD_STATES.OPTIONAL;
                }
                hiddenInput.value = state;
                this.#updateVisualState(fieldId, state);
                delete hiddenInput.dataset.previousState;
            } else {
                if (hiddenInput.value !== FIELD_STATES.DO_NOT_ASK) {
                    hiddenInput.dataset.previousState = hiddenInput.value;
                }
                hiddenInput.value = FIELD_STATES.DO_NOT_ASK;
                this.#updateVisualState(fieldId, FIELD_STATES.DO_NOT_ASK);
            }
        }
    }

    #handleDropdownChange(dropdown) {
        const fieldId = dropdown.dataset.fieldId;
        const hiddenInput = document.getElementById(fieldId);
        const escapedId = fieldId.replace(/(["\\])/g, '\\$1');
        const toggle = document.querySelector(`.toggle-switch[data-field-id="${escapedId}"] input`);

        if (!hiddenInput || !toggle || !toggle.checked) return;

        const newValue = dropdown.value;
        if (!VALID_STATES.includes(newValue)) return;

        hiddenInput.value = newValue;
        this.#updateVisualState(fieldId, newValue);
    }

    #initInfoBoxes() {
        let currentOpenBox = null;

        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('.info-toggle[data-toggle="info-box"]');
            
            if (trigger) {
                const box = trigger.nextElementSibling;
                if (box?.classList.contains('inline-info-box')) {
                    if (currentOpenBox && currentOpenBox !== box) {
                        currentOpenBox.classList.add('d-none');
                    }
                    box.classList.toggle('d-none');
                    currentOpenBox = box.classList.contains('d-none') ? null : box;
                }
                e.stopPropagation();
            } else if (!e.target.closest('.inline-info-box, .info-toggle-wrapper')) {
                if (currentOpenBox) {
                    currentOpenBox.classList.add('d-none');
                    currentOpenBox = null;
                }
            }
        });
    }
}

function initOrderFormToggles() {
    if (!document.querySelector('.order-form-option-table')) {
        return;
    }

    const questionHandler = new QuestionToggleHandler();
    const systemHandler = new SystemFieldHandler();

    questionHandler.initialize();
    systemHandler.initialize();

    console.log('[OrderFormToggles] Initialized successfully');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOrderFormToggles);
} else {
    initOrderFormToggles();
}
