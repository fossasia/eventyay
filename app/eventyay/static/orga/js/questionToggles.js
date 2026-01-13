/**
 * Question toggle handlers
 * Issue #1005: on/off buttons for Required, Active and Public
 */

document.addEventListener('DOMContentLoaded', () => {
    initToggles();
});

function initToggles() {
    // Required status buttons - cycle through states on click
    document.querySelectorAll('.required-status').forEach(btn => {
        btn.addEventListener('click', handleRequiredClick);
    });

    // Binary toggles (active, is_public)
    document.querySelectorAll('.toggle-switch input').forEach(input => {
        input.addEventListener('change', handleBinaryToggle);
    });
}

const REQUIRED_STATES = ['optional', 'required', 'after_deadline'];
const REQUIRED_LABELS = {
    optional: 'Optional',
    required: 'Required',
    after_deadline: 'Deadline'
};

async function handleRequiredClick(e) {
    const btn = e.target.closest('.required-status');
    const questionId = btn.dataset.questionId;
    const currentState = btn.dataset.state;

    // Cycle to next state
    const currentIdx = REQUIRED_STATES.indexOf(currentState);
    const nextState = REQUIRED_STATES[(currentIdx + 1) % REQUIRED_STATES.length];

    btn.classList.add('loading');

    try {
        await updateField(questionId, 'question_required', nextState);
        btn.dataset.state = nextState;
        btn.textContent = REQUIRED_LABELS[nextState];
    } catch (err) {
        console.error('Required toggle failed:', err);
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

    toggle.classList.add('loading');

    try {
        await updateField(questionId, field, value);
    } catch (err) {
        console.error('Toggle failed:', err);
        input.checked = !value;
    } finally {
        toggle.classList.remove('loading');
    }
}

async function updateField(questionId, field, value) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='))?.split('=')[1] || '';

    const response = await fetch(`${questionId}/toggle/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ field, value }),
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
}
