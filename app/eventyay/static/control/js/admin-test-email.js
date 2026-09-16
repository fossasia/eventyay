'use strict';


const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getCsrfToken(form) {
    const input = form.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
}

function setFeedback(feedbackEl, status, message) {
    let alertClass = 'alert alert-danger';
    if (status === 'success') {
        alertClass = 'alert alert-success';
    } else if (status === 'warning') {
        alertClass = 'alert alert-warning';
    }
    feedbackEl.className = alertClass;
    feedbackEl.textContent = message;
    feedbackEl.removeAttribute('hidden');
}

function showLoading(feedbackEl, message) {
    feedbackEl.className = 'alert alert-info';
    feedbackEl.textContent = message;
    feedbackEl.removeAttribute('hidden');
}

function validateRecipients(recipients, input) {
    if (!recipients) {
        return false;
    }
    if (input.checkValidity && !input.checkValidity()) {
        return false;
    }
    const emails = recipients.split(',').map((e) => e.trim()).filter(Boolean);
    if (emails.length === 0) {
        return false;
    }
    return emails.every((e) => EMAIL_REGEX.test(e));
}

async function sendTestEmail(form, input, btn, feedbackEl) {
    if (btn.disabled) return;
    
    const loadingText = btn.dataset.loadingText;
    const invalidText = btn.dataset.invalidText;
    const genericErrorText = btn.dataset.errorText;

    const recipients = input.value.trim();
    if (!validateRecipients(recipients, input)) {
        setFeedback(feedbackEl, 'error', invalidText);
        return;
    }

    btn.disabled = true;
    showLoading(feedbackEl, loadingText);

    const body = new URLSearchParams();
    body.append('test_email', recipients);

    try {
        const response = await fetch(form.action, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': getCsrfToken(form),
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body,
        });

        let data;
        try {
            data = await response.json();
        } catch (e) {
            // JSON parse failed
        }

        if (data && data.message) {
            setFeedback(feedbackEl, data.status || (response.ok ? 'success' : 'error'), data.message);
        } else if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        } else if (data) {
            setFeedback(feedbackEl, data.status || 'success', data.message || '');
        } else {
            throw new Error('Invalid JSON response');
        }
    } catch (err) {
        console.error('Test email request failed:', err);
        setFeedback(feedbackEl, 'error', genericErrorText);
    } finally {
        btn.disabled = false;
    }
}

function init() {
    const btn = document.getElementById('admin-test-email-btn');
    if (!btn) {
        return;
    }

    const form = document.getElementById('admin-test-email-form');
    const input = document.getElementById('admin-test-email-input');
    const feedbackEl = document.getElementById('admin-test-email-feedback');

    if (!form || !input || !feedbackEl) {
        return;
    }

    const triggerSend = (e) => {
        e.preventDefault();
        sendTestEmail(form, input, btn, feedbackEl);
    };

    btn.addEventListener('click', triggerSend);
    form.addEventListener('submit', triggerSend);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            triggerSend(e);
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
