(function () {
    function gettext(msgid) {
        if (typeof django !== 'undefined' && typeof django.gettext === 'function') {
            return django.gettext(msgid);
        }
        if (typeof gettext === 'function') {
            return gettext(msgid);
        }
        return msgid;
    }

    function interpolate(template, params) {
        return Object.keys(params).reduce(function (message, key) {
            return message.replace(new RegExp('%\\(' + key + '\\)s', 'g'), String(params[key]));
        }, template);
    }

    function readJsonScript(id) {
        const element = document.getElementById(id);
        if (!element || !element.textContent) {
            return {};
        }
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return {};
        }
    }

    function getChanges(form) {
        const changes = [];
        form.querySelectorAll('.js-video-feature-toggle').forEach(function (checkbox) {
            const initial = checkbox.dataset.initialValue === '1';
            if (checkbox.checked === initial) {
                return;
            }
            changes.push({
                fieldName: checkbox.name,
                enabling: checkbox.checked,
            });
        });
        return changes;
    }

    function formatUsage(rooms, events) {
        return interpolate(
            gettext('Used by %(rooms)s %(roomLabel)s in %(events)s %(eventLabel)s'),
            {
                rooms: rooms,
                events: events,
                roomLabel: rooms === 1 ? gettext('room') : gettext('rooms'),
                eventLabel: events === 1 ? gettext('event') : gettext('events'),
            }
        );
    }

    function buildSaveConfirmOptions(changes, labels, usage) {
        const messageParts = [
            gettext('Apply the following changes to video component availability?'),
            '',
        ];

        changes.forEach(function (change) {
            const label = labels[change.fieldName] || change.fieldName;
            const componentUsage = usage[change.fieldName] || {};

            if (change.enabling) {
                messageParts.push(
                    '• ' + interpolate(gettext('Enable %(component)s'), { component: label })
                );
                return;
            }

            messageParts.push(
                '• ' + interpolate(gettext('Disable %(component)s'), { component: label })
            );
            if (componentUsage.rooms > 0) {
                messageParts.push(
                    '  ' + formatUsage(componentUsage.rooms, componentUsage.events)
                );
            }
        });

        const hasInUseDisables = changes.some(function (change) {
            if (change.enabling) {
                return false;
            }
            const componentUsage = usage[change.fieldName] || {};
            return componentUsage.rooms > 0;
        });

        if (hasInUseDisables) {
            messageParts.push('');
            messageParts.push(
                gettext(
                    'Existing configuration for disabled components will be kept, but organizers ' +
                    'will no longer be able to create or use them while they are disabled.'
                )
            );
        }

        return {
            title: hasInUseDisables
                ? gettext('Confirm video component changes')
                : gettext('Save video component settings'),
            message: messageParts.join('\n'),
            confirmLabel: hasInUseDisables ? gettext('Confirm and save') : gettext('Save'),
            cancelLabel: gettext('Cancel'),
            confirmClass: hasInUseDisables ? 'btn-danger' : 'btn-primary',
            hasInUseDisables: hasInUseDisables,
        };
    }

    function ensureConfirmDisableField(form) {
        let field = form.querySelector('input[name="confirm_disable"]');
        if (!field) {
            field = document.createElement('input');
            field.type = 'hidden';
            field.name = 'confirm_disable';
            form.appendChild(field);
        }
        field.value = '1';
    }

    async function handleFormSubmit(event) {
        const form = event.target;
        if (!form.matches('#video-features-form')) {
            return;
        }
        if (form.dataset.confirmBypass === '1') {
            form.dataset.confirmBypass = '';
            return;
        }

        const changes = getChanges(form);
        if (!changes.length) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        const labels = readJsonScript('video-feature-labels');
        const usage = readJsonScript('video-feature-usage');
        const options = buildSaveConfirmOptions(changes, labels, usage);

        const confirmed = window.showConfirmDialog
            ? await window.showConfirmDialog(options)
            : window.confirm(options.message);

        if (!confirmed) {
            return;
        }

        if (options.hasInUseDisables) {
            ensureConfirmDisableField(form);
        }

        form.dataset.confirmBypass = '1';
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    function init() {
        const form = document.getElementById('video-features-form');
        if (!form) {
            return;
        }

        form.querySelectorAll('.js-video-feature-toggle').forEach(function (checkbox) {
            checkbox.dataset.initialValue = checkbox.checked ? '1' : '0';
        });

        form.addEventListener('submit', handleFormSubmit);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
