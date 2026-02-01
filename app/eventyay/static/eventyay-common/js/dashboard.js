$(function () {
    // Defensive check for i18n functions
    if (typeof gettext === 'undefined') {
        window.gettext = function (msg) { return msg; };
    }
    if (typeof interpolate === 'undefined') {
        window.interpolate = function (msg, params) { return msg; };
    }
    // Helper to get CSRF token from cookies if not in DOM
    function getCookie(name) {
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
    }

    $('.dashboard').on('click', '.mode-btn', function (e) {
        e.preventDefault();
        const btn = $(this);
        const component = btn.data('component');
        const mode = btn.data('mode');
        const eventSlug = btn.data('event-slug');
        const organizerSlug = btn.data('organizer-slug');

        let title = '';
        let body = '';
        let actions = [];

        if (component === 'tickets') {
            title = gettext('Tickets Mode');
            if (mode === 'offline') {
                body = gettext('Currently Offline. Enable Test Mode to start testing ticket sales.');
                actions.push({ label: gettext('Enable Test Mode'), mode: 'test', class: 'btn-info' });
            } else if (mode === 'test') {
                body = gettext('Currently in Test Mode. Go Live to start real ticket sales.');
                actions.push({ label: gettext('Go Live'), mode: 'live', class: 'btn-success' });
            } else if (mode === 'live') {
                body = gettext('Currently Live. You can return to Offline mode if needed.');
                actions.push({ label: gettext('Go Offline'), mode: 'offline', class: 'btn-danger' });
            }
        } else if (component === 'talks' || component === 'video') {
            const compLabel = component === 'talks' ? gettext('Talks') : gettext('Video');
            title = compLabel + ' ' + gettext('Mode');
            if (mode === 'offline') {
                body = interpolate(gettext('Currently %s is Offline. Make it Live to enable access.'), [compLabel]);
                actions.push({ label: gettext('Make Live'), mode: 'live', class: 'btn-success' });
            } else {
                body = interpolate(gettext('Currently %s is Live.'), [compLabel]);
                actions.push({ label: gettext('Go Offline'), mode: 'offline', class: 'btn-danger' });
            }
        }

        $('#mode-modal-title').text(title);
        $('#mode-modal-body').text(body);
        const footer = $('#mode-modal-footer');
        footer.find('.action-btn').remove();

        actions.forEach(action => {
            const actionBtn = $('<button>')
                .addClass('btn action-btn ' + action.class)
                .text(action.label)
                .on('click', function () {
                    updateMode(organizerSlug, eventSlug, component, action.mode, btn);
                });
            footer.append(actionBtn);
        });

        $('#mode-modal').modal('show');
    });

    function updateMode(organizerSlug, eventSlug, component, mode, btn) {
        const url = `/common/event/${organizerSlug}/${eventSlug}/component-modes/`;

        let csrfToken = $('meta[name="csrf-token"]').attr('content');
        if (!csrfToken) {
            csrfToken = getCookie('csrftoken');
        }

        $.ajax({
            url: url,
            method: 'POST',
            data: {
                'component': component,
                'mode': mode,
                'csrfmiddlewaretoken': csrfToken
            },
            success: function (data) {
                $('#mode-modal').modal('hide');
                if (data.status === 'success') {
                    const newMode = data.new_mode;
                    btn.removeClass('mode-offline mode-test mode-live')
                        .addClass('mode-' + newMode);
                    btn.data('mode', newMode);
                    btn.attr('data-mode', newMode);
                    const modeLabels = {
                        'offline': gettext('Offline'),
                        'test': gettext('Test'),
                        'live': gettext('Live')
                    };
                    let label = modeLabels[newMode];
                    if (!label) {
                        label = newMode.charAt(0).toUpperCase() + newMode.slice(1);
                    }
                    btn.text(label);
                } else {
                    location.reload();
                }
            },
            error: function (xhr) {
                let msg = gettext('An error occurred.');
                if (xhr.status === 403) {
                    msg = gettext('Permission denied or CSRF failure.');
                } else if (xhr.responseJSON && xhr.responseJSON.error) {
                    msg = xhr.responseJSON.error;
                } else if (xhr.status && xhr.statusText) {
                    msg += ' (' + xhr.status + ': ' + xhr.statusText + ')';
                }
                $('#mode-modal-title').text(gettext('Error'));
                $('#mode-modal-body').html(msg);
                $('#mode-modal-footer').find('.action-btn').remove();
            }
        });
    }
});
