function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function showAlert(message, type = 'success') {
    const existingAlert = document.querySelector('.admin-users-alert');
    if (existingAlert) {
        existingAlert.remove();
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} admin-users-alert`;
    alert.setAttribute('role', 'alert');
    alert.textContent = message;

    const table = document.querySelector('.admin-users-table');
    if (table && table.parentNode) {
        table.parentNode.insertBefore(alert, table);
    }

    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 4000);
}

async function handleToggleChange(event) {
    const checkbox = event.currentTarget;
    const form = checkbox.closest('.user-toggle-form');
    if (!form) return;

    const toggleType = form.dataset.toggleType;
    const isChecked = checkbox.checked;

    if (toggleType === 'admin' && isChecked) {
        const confirmMessage = form.dataset.confirmMessage
            || 'Please confirm that this account should be a site admin.';
        if (!window.confirm(confirmMessage)) {
            checkbox.checked = !isChecked;
            return;
        }
    }

    const label = checkbox.closest('.toggle-switch');
    if (label) {
        label.classList.add('loading');
    }
    checkbox.disabled = true;

    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new FormData(form),
        });

        const contentType = response.headers.get('content-type');
        let data = {};
        if (contentType && contentType.indexOf('application/json') !== -1) {
            data = await response.json();
        } else {
            checkbox.checked = !isChecked;
            showAlert('Session expired or access denied. Please refresh the page.', 'danger');
            return;
        }

        if (response.ok && data.status === 'ok') {
            let newValue;
            if (toggleType === 'verified') {
                newValue = data.is_verified;
            } else if (toggleType === 'admin') {
                newValue = data.is_staff;
            } else if (toggleType === 'spam') {
                newValue = data.is_spam;
            }

            checkbox.checked = newValue;
            showAlert(getSuccessMessage(toggleType, newValue), 'success');
        } else {
            checkbox.checked = !isChecked;
            showAlert(data.message || 'An error occurred. Please try again.', 'danger');
        }
    } catch (err) {
        checkbox.checked = !isChecked;
        showAlert('Network error. Please try again.', 'danger');
    } finally {
        if (label) {
            label.classList.remove('loading');
        }
        checkbox.disabled = false;
    }
}

function getSuccessMessage(toggleType, newValue) {
    const messages = {
        verified: newValue ? 'User marked as verified.' : 'User marked as unverified.',
        admin: newValue ? 'Admin role granted.' : 'Admin role removed.',
        spam: newValue ? 'User marked as spam.' : 'User unmarked as spam.',
    };
    return messages[toggleType] || 'Action completed successfully.';
}

async function handleActionSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');

    if (button) {
        button.disabled = true;
    }

    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new FormData(form),
        });

        const contentType = response.headers.get('content-type');
        let data = {};
        if (contentType && contentType.indexOf('application/json') !== -1) {
            data = await response.json();
        } else {
            showAlert('Session expired or access denied. Please refresh the page.', 'danger');
            return;
        }

        if (response.ok && data.status === 'ok') {
            showAlert('Email sent successfully.', 'success');
        } else {
            showAlert(data.message || 'An error occurred. Please try again.', 'danger');
        }
    } catch (err) {
        showAlert('Network error. Please try again.', 'danger');
    } finally {
        if (button) {
            button.disabled = false;
        }
    }
}

function init() {
    document.querySelectorAll('.user-toggle-form').forEach((form) => {
        form.addEventListener('submit', (e) => e.preventDefault());
        const checkbox = form.querySelector('.js-user-toggle');
        if (checkbox) {
            checkbox.addEventListener('change', handleToggleChange);
        }
    });

    document.querySelectorAll('.user-action-form').forEach((form) => {
        form.addEventListener('submit', handleActionSubmit);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
