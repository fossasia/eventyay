(function() {
    'use strict';

    function init() {
        const csrfTokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        
        function getCsrfToken() {
            if (csrfTokenInput) {
                return csrfTokenInput.value;
            }
            // Fallback to cookie
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, 19) === 'eventyay_csrftoken=') {
                        cookieValue = decodeURIComponent(cookie.substring(19));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        // ==========================================
        // AJAX DELETION
        // ==========================================
        const deleteButtons = document.querySelectorAll('.btn-delete-image-ajax');

        function getSettingKey(button) {
            const fieldName = button.getAttribute('data-field') || '';
            if (fieldName.startsWith('settings-')) {
                return fieldName.substring('settings-'.length);
            }

            return '';
        }
        
        // Show AJAX delete buttons and hide standard delete checkboxes ONLY for settings fields
        deleteButtons.forEach(button => {
            const settingKey = getSettingKey(button);
            if (settingKey) {
                button.style.display = 'inline-block';
                const container = button.closest('.initial-file-container');
                if (container) {
                    const checkboxWrapper = container.querySelector('.delete-checkbox-wrapper');
                    if (checkboxWrapper) {
                        checkboxWrapper.style.display = 'none';
                    }
                }
            }
        });
        
        function revertButton(button) {
            button.dataset.confirming = 'false';
            const icon = button.querySelector('i');
            if (icon) {
                icon.className = 'fa fa-trash';
            }
            if (button.dataset.originalTitle !== undefined) {
                button.setAttribute('title', button.dataset.originalTitle);
            }
            if (button.dataset.originalClass) {
                button.className = button.dataset.originalClass;
            }
            if (button.dataset.timeoutId) {
                clearTimeout(parseInt(button.dataset.timeoutId));
                delete button.dataset.timeoutId;
            }
            if (button.dataset.intervalId) {
                clearInterval(parseInt(button.dataset.intervalId));
                delete button.dataset.intervalId;
            }
            const container = button.closest('.initial-file-container') || button.parentNode;
            const msgSpan = container.querySelector('.delete-confirm-msg');
            if (msgSpan) {
                msgSpan.style.display = 'none';
            }
        }

        deleteButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const fieldName = button.getAttribute('data-field');
                const settingKey = getSettingKey(button);
                if (!fieldName || !settingKey) return;

                if (button.dataset.confirming !== 'true') {
                    // Enter confirming state
                    button.dataset.confirming = 'true';
                    button.dataset.originalTitle = button.getAttribute('title') || '';
                    button.dataset.originalClass = button.className;

                    button.className = 'btn btn-warning btn-xs btn-delete-image-ajax';
                    const icon = button.querySelector('i');
                    if (icon) {
                        icon.className = 'fa fa-trash';
                    }
                    const confirmText = window.i18n ? window.i18n.gettext('Click again to confirm') : 'Click again to confirm';
                    button.setAttribute('title', confirmText);

                    const container = button.closest('.initial-file-container') || button.parentNode;
                    let msgSpan = container.querySelector('.delete-confirm-msg');
                    if (!msgSpan) {
                        msgSpan = document.createElement('span');
                        msgSpan.className = 'delete-confirm-msg text-warning small';
                        msgSpan.style.cssText = 'margin-left: 8px; font-weight: 500; vertical-align: middle;';
                        button.parentNode.insertBefore(msgSpan, button.nextSibling);
                    }

                    let secondsLeft = 3;
                    msgSpan.textContent = `${confirmText} (${secondsLeft}s)`;
                    msgSpan.className = 'delete-confirm-msg text-warning small';
                    msgSpan.style.display = 'inline-block';

                    const intervalId = setInterval(() => {
                        secondsLeft--;
                        if (secondsLeft > 0) {
                            msgSpan.textContent = `${confirmText} (${secondsLeft}s)`;
                        }
                    }, 1000);
                    button.dataset.intervalId = intervalId;

                    // Automatically revert after 3 seconds of inactivity
                    const timeoutId = setTimeout(() => {
                        revertButton(button);
                    }, 3000);
                    button.dataset.timeoutId = timeoutId;
                    return;
                }

                // If already confirming, proceed with deletion
                if (button.dataset.timeoutId) {
                    clearTimeout(parseInt(button.dataset.timeoutId));
                    delete button.dataset.timeoutId;
                }
                if (button.dataset.intervalId) {
                    clearInterval(parseInt(button.dataset.intervalId));
                    delete button.dataset.intervalId;
                }
                const container = button.closest('.initial-file-container') || button.parentNode;
                const msgSpan = container.querySelector('.delete-confirm-msg');
                if (msgSpan) {
                    msgSpan.className = 'delete-confirm-msg text-danger small';
                    msgSpan.textContent = window.i18n ? window.i18n.gettext('Deleting...') : 'Deleting...';
                }

                button.disabled = true;
                button.className = 'btn btn-danger btn-xs btn-delete-image-ajax';
                const icon = button.querySelector('i');
                if (icon) {
                    icon.className = 'fa fa-spinner fa-spin';
                }

                const params = new URLSearchParams();
                params.append('ajax', 'delete_image');
                params.append('field', fieldName);
                params.append('setting_key', settingKey);

                fetch(window.location.pathname + window.location.search, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: params
                })
                .then(response => {
                    if (!response.ok) {
                        return response.text().then(text => {
                            throw new Error(text || `Request failed with status ${response.status}`);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // Successfully deleted on server, update DOM
                        const container = button.closest('.initial-file-container');
                        if (container) {
                            container.style.display = 'none';
                            // Also hide the "Change:" text container if it exists next to it
                            const labelText = container.nextElementSibling;
                            if (labelText && labelText.classList.contains('input-text-container')) {
                                labelText.style.display = 'none';
                            }
                        }

                        // Update the data-image-source-pair dataset state to indicate there's no uploaded file
                        const pair = button.closest('[data-image-source-pair]');
                        if (pair) {
                            pair.dataset.hasCurrentFile = 'false';
                            pair.setAttribute('data-has-current-file', 'false');
                        }
                    } else {
                        alert(data.error || 'Failed to delete the image.');
                        revertButton(button);
                        button.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('AJAX Deletion Error:', error);
                    alert(error.message || 'An error occurred while deleting the image.');
                    revertButton(button);
                    button.disabled = false;
                });
            });
        });
    }

    // Script is loaded at the bottom of <body>, so DOMContentLoaded may have
    // already fired. Run init immediately if the DOM is ready, otherwise defer.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
