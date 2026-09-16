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
    const match = document.cookie.match(/(?:^|;\s*)eventyay_csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

let pendingAdminAction = null;

function showAlert(message, type = 'success', { autoDismiss = true } = {}) {
    const region = document.querySelector('.admin-users-alert-region');
    if (!region) return;

    region.querySelector('.admin-users-alert')?.remove();

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible admin-users-alert`;
    alert.setAttribute('role', type === 'danger' ? 'alert' : 'status');

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'close';
    closeButton.setAttribute('aria-label', gettext('Close'));
    closeButton.innerHTML = '<span aria-hidden="true">&times;</span>';
    closeButton.addEventListener('click', () => alert.remove());

    const text = document.createElement('span');
    text.textContent = message;

    alert.append(closeButton, text);
    region.append(alert);

    if (autoDismiss) {
        setTimeout(() => alert.remove(), 6000);
    }
}

async function handleToggleChange(event) {
    const checkbox = event.target;
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

async function handleActionClick(button) {
    const form = getClosest(button, 'form');
    if (!form || form.getAttribute('aria-busy') === 'true') return;

    const errorMessage = form.dataset.errorMessage || gettext('An error occurred. Please try again.');
    const icon = button.querySelector('.fa');
    const originalIconClasses = icon ? icon.className : '';
    const label = button.querySelector('.user-action-label');
    const originalLabel = label ? label.textContent : '';

    const row = getClosest(form, 'tr');
    const toggle = row?.querySelector('.user-email-actions-toggle');
    const toggleIcon = toggle?.querySelector('.fa');
    const originalToggleIconClasses = toggleIcon ? toggleIcon.className : '';

    form.setAttribute('aria-busy', 'true');
    button.disabled = true;
    if (icon) {
        icon.className = 'fa fa-spinner fa-spin';
    }
    if (label && form.dataset.pendingMessage) {
        label.textContent = form.dataset.pendingMessage;
    }
    if (toggle) {
        toggle.disabled = true;
    }
    if (toggleIcon) {
        toggleIcon.className = 'fa fa-spinner fa-spin';
    }
    if (form.dataset.pendingMessage) {
        showAlert(form.dataset.pendingMessage, 'info', { autoDismiss: false });
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
        if (!contentType || !contentType.includes('application/json')) {
            showAlert(gettext('Session expired or access denied. Please refresh the page.'), 'danger', { autoDismiss: false });
            return;
        }

        const data = await response.json();
        if (response.ok && data.status === 'ok') {
            showAlert(data.message || gettext('Email sent successfully.'), 'success');
        } else {
            showAlert(data.message || errorMessage, 'danger', { autoDismiss: false });
        }
    } catch (err) {
        console.error('Admin user email action failed', { action: form.elements.action?.value, error: err });
        showAlert(errorMessage, 'danger', { autoDismiss: false });
    } finally {
        if (icon) {
            icon.className = originalIconClasses;
        }
        if (label) {
            label.textContent = originalLabel;
        }
        if (toggle) {
            toggle.disabled = false;
        }
        if (toggleIcon) {
            toggleIcon.className = originalToggleIconClasses;
        }
        button.disabled = false;
        form.removeAttribute('aria-busy');
    }
}

/* The results table is swapped out by ajax-filter.js on search, filter, sort and
 * pagination, so listeners are delegated from the document instead of being bound
 * to the rows present at page load. */
function init() {
    document.addEventListener('submit', (event) => {
        if (event.target.matches('.user-toggle-form, .user-action-form')) {
            event.preventDefault();
        }
    });

    document.addEventListener('change', (event) => {
        if (event.target.matches('.user-toggle-form .js-user-toggle')) {
            handleToggleChange(event);
        }
    });

    document.addEventListener('click', (event) => {
        const button = event.target.closest('.user-action-form button');
        if (button) {
            event.preventDefault();
            handleActionClick(button);
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
