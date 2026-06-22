function getClosest(element, selector) {
    let current = element;
    while (current && current !== document) {
        if (current.matches && current.matches(selector)) {
            return current;
        }
        current = current.parentElement;
    }
    return null;
}

function gettext(msgid) {
    if (typeof django !== 'undefined' && typeof django.gettext === 'function') {
        return django.gettext(msgid);
    }
    return msgid;
}

function getCsrfToken(form) {
    if (form) {
        const input = form.querySelector('[name=csrfmiddlewaretoken]');
        if (input) {
            return input.value;
        }
    }
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

let pendingAdminAction = null;

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
    const form = getClosest(checkbox, 'form');
    if (!form) return;

    const toggleType = form.dataset.toggleType;
    const isChecked = checkbox.checked;

    if (toggleType === 'admin' && isChecked) {
        const confirmMessage = form.dataset.confirmMessage
            || gettext('Please confirm that this account should be a site admin.');
        const dialog = document.getElementById('admin-confirm-dialog');
        if (dialog && typeof dialog.showModal === 'function') {
            document.getElementById('admin-confirm-message').textContent = confirmMessage;
            pendingAdminAction = { form, checkbox, isChecked };
            dialog.showModal();
        } else {
            if (window.confirm(confirmMessage)) {
                await submitToggle(form, checkbox, isChecked);
            } else {
                checkbox.checked = !isChecked;
            }
        }
        return;
    }

    await submitToggle(form, checkbox, isChecked);
}

async function submitToggle(form, checkbox, isChecked) {
    const toggleType = form.dataset.toggleType;
    const label = checkbox.parentElement;
    if (label) {
        label.classList.add('loading');
    }
    checkbox.disabled = true;

    try {
        const response = await fetch(form.getAttribute('action'), {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(form),
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
            showAlert(gettext('Session expired or access denied. Please refresh the page.'), 'danger');
            return;
        }

        if (response.ok && data.status === 'ok') {
            let newValue;
            if (toggleType === 'verified') {
                newValue = data.is_verified;
                if (label) {
                    label.title = newValue ? gettext('Unverify') : gettext('Verify');
                }
            } else if (toggleType === 'admin' || toggleType === 'admin_confirmed') {
                newValue = data.is_staff;
                if (label) {
                    label.title = newValue ? gettext('Remove admin') : gettext('Make admin');
                }
            } else if (toggleType === 'spam') {
                newValue = data.is_spam;
                if (label) {
                    label.title = newValue ? gettext('Unmark spam') : gettext('Mark as spam');
                }
            }

            checkbox.checked = newValue;

            if (toggleType === 'admin' || toggleType === 'admin_confirmed') {
                const row = getClosest(checkbox, 'tr');
                if (row) {
                    const spamForm = row.querySelector('.user-toggle-form[data-toggle-type="spam"]');
                    if (spamForm) {
                        const spamCheckbox = spamForm.querySelector('.js-user-toggle');
                        const spamLabel = spamCheckbox?.parentElement;
                        if (spamCheckbox && spamLabel) {
                            if (newValue) {
                                spamCheckbox.checked = false;
                                spamCheckbox.disabled = true;
                                spamLabel.classList.add('always-on');
                                spamLabel.title = gettext('Administrators cannot be marked as spam.');
                            } else {
                                spamCheckbox.disabled = false;
                                spamLabel.classList.remove('always-on');
                                spamLabel.title = gettext('Mark as spam');
                            }
                        }
                    }
                }
            }

            showAlert(getSuccessMessage(toggleType.replace('_confirmed', ''), newValue), 'success');
        } else {
            checkbox.checked = !isChecked;
            showAlert(data.message || gettext('An error occurred. Please try again.'), 'danger');
        }
    } catch (err) {
        checkbox.checked = !isChecked;
        showAlert(gettext('Network error. Please try again.'), 'danger');
    } finally {
        if (label) {
            label.classList.remove('loading');
        }
        checkbox.disabled = false;
    }
}

const adminDialog = document.getElementById('admin-confirm-dialog');

if (adminDialog) {
    adminDialog.addEventListener('close', () => {
        if (!pendingAdminAction) {
            adminDialog.returnValue = '';
            return;
        }

        if (adminDialog.returnValue === 'confirm') {
            const { form, checkbox, isChecked } = pendingAdminAction;
            pendingAdminAction = null;
            adminDialog.returnValue = '';
            form.dataset.toggleType = 'admin_confirmed';
            submitToggle(form, checkbox, isChecked).finally(() => {
                form.dataset.toggleType = 'admin';
            });
        } else {
            pendingAdminAction.checkbox.checked = !pendingAdminAction.isChecked;
            pendingAdminAction = null;
            adminDialog.returnValue = '';
        }
    });

    document.getElementById('admin-confirm-btn')?.addEventListener('click', () => {
        adminDialog.close('confirm');
    });

    document.getElementById('admin-cancel-btn')?.addEventListener('click', () => {
        adminDialog.close();
    });
}

function getSuccessMessage(toggleType, newValue) {
    const messages = {
        verified: newValue ? gettext('User marked as verified.') : gettext('User marked as unverified.'),
        admin: newValue ? gettext('Admin role granted.') : gettext('Admin role removed.'),
        spam: newValue ? gettext('User marked as spam.') : gettext('User unmarked as spam.'),
    };
    return messages[toggleType] || gettext('Action completed successfully.');
}

async function handleActionClick(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const form = getClosest(button, 'form');
    if (!form) return;

    const icon = button.querySelector('.fa');
    const originalClasses = icon ? icon.className : '';

    button.disabled = true;
    if (icon) {
        icon.className = 'fa fa-spinner fa-spin';
    }

    try {
        const response = await fetch(form.getAttribute('action'), {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(form),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new FormData(form),
        });

        const contentType = response.headers.get('content-type');
        let data = {};
        if (contentType && contentType.indexOf('application/json') !== -1) {
            data = await response.json();
        } else {
            showAlert(gettext('Session expired or access denied. Please refresh the page.'), 'danger');
            return;
        }

        if (response.ok && data.status === 'ok') {
            showAlert(data.message || gettext('Email sent successfully.'), 'success');
        } else {
            showAlert(data.message || gettext('An error occurred. Please try again.'), 'danger');
        }
    } catch (err) {
        showAlert(gettext('Network error. Please try again.'), 'danger');
    } finally {
        if (icon) {
            icon.className = originalClasses;
        }
        button.disabled = false;
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

    document.querySelectorAll('.user-action-form button').forEach((button) => {
        button.addEventListener('click', handleActionClick);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
