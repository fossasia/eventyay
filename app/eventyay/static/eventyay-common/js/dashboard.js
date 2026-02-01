'use strict';
// Defensive check for i18n functions
if (typeof gettext === 'undefined') {
    window.gettext = function (msg) { return msg; };
}
if (typeof interpolate === 'undefined') {
    window.interpolate = function (msg, params) { return msg; };
}

const getCookie = function (name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};

/**
 * Get the CSRF token from meta tag or cookie
 * @returns {string|null} - CSRF token
 */
const getCSRFToken = function () {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return getCookie('csrftoken');
};

/**
 * Show Bootstrap modal (compatible with Bootstrap 3)
 * @param {string} modalId - Modal element ID
 */
const showModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal && typeof $ !== 'undefined' && $.fn && $.fn.modal) {
        $('#' + modalId).modal('show');
    }
};

/**
 * Hide Bootstrap modal (compatible with Bootstrap 3)
 * @param {string} modalId - Modal element ID
 */
const hideModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal && typeof $ !== 'undefined' && $.fn && $.fn.modal) {
        $('#' + modalId).modal('hide');
    }
};

/**
 * Update component mode via API
 * @param {string} organizerSlug - Organizer slug
 * @param {string} eventSlug - Event slug
 * @param {string} component - Component type (tickets, talks, video)
 * @param {string} mode - New mode (offline, test, live)
 * @param {HTMLElement} btn - Button element to update
 */
const updateMode = function (organizerSlug, eventSlug, component, mode, btn) {
    const url = `/common/event/${organizerSlug}/${eventSlug}/component-modes/`;
    const csrfToken = getCSRFToken();

    const formData = new FormData();
    formData.append('component', component);
    formData.append('mode', mode);
    formData.append('csrfmiddlewaretoken', csrfToken);

    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
        .then(function (response) {
            if (!response.ok) {
                if (response.status === 403) {
                    throw new Error(gettext('Permission denied or CSRF failure.'));
                }
                return response.json().then(function (data) {
                    throw new Error(data.error || response.status + ': ' + response.statusText);
                }).catch(function (err) {
                    if (err.message) throw err;
                    throw new Error(response.status + ': ' + response.statusText);
                });
            }
            return response.json();
        })
        .then(function (data) {
            hideModal('mode-modal');

            if (data.status === 'success') {
                const newMode = data.new_mode;
                btn.classList.remove('mode-offline', 'mode-test', 'mode-live');
                btn.classList.add('mode-' + newMode);
                btn.dataset.mode = newMode;
                btn.setAttribute('data-mode', newMode);

                const modeLabels = {
                    'offline': gettext('Offline'),
                    'test': gettext('Test'),
                    'live': gettext('Live')
                };
                let label = modeLabels[newMode];
                if (!label) {
                    label = newMode.charAt(0).toUpperCase() + newMode.slice(1);
                }
                btn.textContent = label;
            } else {
                location.reload();
            }
        })
        .catch(function (error) {
            const titleEl = document.getElementById('mode-modal-title');
            const bodyEl = document.getElementById('mode-modal-body');
            const footerEl = document.getElementById('mode-modal-footer');

            titleEl.textContent = gettext('Error');
            bodyEl.innerHTML = error.message || gettext('An error occurred.');

            // Remove action buttons on error
            footerEl.querySelectorAll('.action-btn').forEach(function (el) {
                el.remove();
            });
        });
};

/**
 * Handle mode button click - show modal with appropriate options
 * @param {Event} e - Click event
 */
const handleModeButtonClick = function (e) {
    e.preventDefault();

    const btn = e.target.closest('.mode-btn');
    if (!btn) return;

    const component = btn.dataset.component;
    const mode = btn.dataset.mode;
    const eventSlug = btn.dataset.eventSlug;
    const organizerSlug = btn.dataset.organizerSlug;

    let title = '';
    let body = '';
    let actions = [];

    if (component === 'tickets') {
        title = gettext('Tickets Mode');
        if (mode === 'offline') {
            body = gettext('Currently Offline. Enable Test Mode to start testing ticket sales.');
            actions.push({ label: gettext('Enable Test Mode'), mode: 'test', className: 'btn-info' });
        } else if (mode === 'test') {
            body = gettext('Currently in Test Mode. Go Live to start real ticket sales, or go back to Offline.');
            actions.push({ label: gettext('Go Offline'), mode: 'offline', className: 'btn-danger' });
            actions.push({ label: gettext('Go Live'), mode: 'live', className: 'btn-success' });
        } else if (mode === 'live') {
            body = gettext('Currently Live. You can return to Offline mode if needed.');
            actions.push({ label: gettext('Go Offline'), mode: 'offline', className: 'btn-danger' });
        }
    } else if (component === 'talks' || component === 'video') {
        const compLabel = component === 'talks' ? gettext('Talks') : gettext('Video');
        title = compLabel + ' ' + gettext('Mode');
        if (mode === 'offline') {
            body = interpolate(gettext('Currently %s is Offline. Make it Live to enable access.'), [compLabel]);
            actions.push({ label: gettext('Make Live'), mode: 'live', className: 'btn-success' });
        } else {
            body = interpolate(gettext('Currently %s is Live.'), [compLabel]);
            actions.push({ label: gettext('Go Offline'), mode: 'offline', className: 'btn-danger' });
        }
    }

    const titleEl = document.getElementById('mode-modal-title');
    const bodyEl = document.getElementById('mode-modal-body');
    const footerEl = document.getElementById('mode-modal-footer');

    titleEl.textContent = title;
    bodyEl.textContent = body;

    // Remove existing action buttons
    footerEl.querySelectorAll('.action-btn').forEach(function (el) {
        el.remove();
    });

    // Create new action buttons
    actions.forEach(function (action) {
        const actionBtn = document.createElement('button');
        actionBtn.className = 'btn action-btn ' + action.className;
        actionBtn.textContent = action.label;
        actionBtn.addEventListener('click', function () {
            updateMode(organizerSlug, eventSlug, component, action.mode, btn);
        });
        footerEl.appendChild(actionBtn);
    });

    showModal('mode-modal');
};

/**
 * Initialize dashboard event listeners
 */
const initDashboard = function () {
    const dashboard = document.querySelector('.dashboard');
    if (dashboard) {
        // Use event delegation for mode buttons
        dashboard.addEventListener('click', function (e) {
            if (e.target.closest('.mode-btn')) {
                handleModeButtonClick(e);
            }
        });
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}

export { initDashboard };
