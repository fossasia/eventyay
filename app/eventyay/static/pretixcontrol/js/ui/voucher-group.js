const formSelector = '[data-voucher-group-form]';

function gettextSafe(msgid) {
    if (typeof gettext === 'function') {
        return gettext(msgid);
    }
    return msgid;
}

function initVoucherGroupForm() {
    const form = document.querySelector(formSelector);
    if (!form) {
        return;
    }

    form.addEventListener('submit', async function (event) {
        if (form.dataset.confirmed === '1') {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        if (typeof form.reportValidity === 'function' && !form.reportValidity()) {
            return;
        }

        const submitBtn = form.querySelector('.btn-save');
        if (submitBtn) {
            submitBtn.disabled = true;
        }

        const initialQuery = new URLSearchParams(new FormData(form)).toString();
        const editableControls = Array.from(
            form.querySelectorAll('input:not([type="hidden"]), select, textarea')
        );
        editableControls.forEach((el) => {
            el.dataset.prevReadonly = el.readOnly ? '1' : '0';
            el.readOnly = true;
        });

        try {
            const formData = new FormData(form);
            formData.append('ajax_preview', '1');

            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            const data = await response.json();

            if (!data.success) {
                if (data.error) {
                    if (typeof window.showConfirmDialog === 'function') {
                        await window.showConfirmDialog({
                            title: gettextSafe('Error'),
                            message: data.error,
                            confirmLabel: gettextSafe('OK'),
                            confirmClass: 'btn-danger',
                        });
                    } else {
                        window.alert(data.error);
                    }
                } else {
                    form.dataset.confirmed = '1';
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        form.submit();
                    }
                }
                return;
            }

            const title = form.dataset.confirmTitle || gettextSafe('Confirm voucher updates');
            const confirmLabel = form.dataset.confirmLabel || gettextSafe('Confirm and save');
            const cancelLabel = form.dataset.cancelLabel || gettextSafe('Cancel');

            let confirmed = false;
            const message = data.html_message || data.message;
            if (typeof window.showConfirmDialog === 'function') {
                confirmed = await window.showConfirmDialog({
                    title: title,
                    message: message,
                    isHtml: Boolean(data.html_message),
                    confirmLabel: confirmLabel,
                    cancelLabel: cancelLabel,
                    confirmClass: 'btn-primary',
                });
            } else {
                confirmed = window.confirm(data.message);
            }

            if (confirmed) {
                const currentQuery = new URLSearchParams(new FormData(form)).toString();
                if (currentQuery !== initialQuery) {
                    delete form.dataset.confirmed;
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        form.submit();
                    }
                    return;
                }

                let confirmInput = form.querySelector('input[name="confirm"]');
                if (!confirmInput) {
                    confirmInput = document.createElement('input');
                    confirmInput.type = 'hidden';
                    confirmInput.name = 'confirm';
                    form.appendChild(confirmInput);
                }
                confirmInput.value = '1';
                form.dataset.confirmed = '1';
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            }
        } catch (err) {
            console.error('Failed to preview voucher group updates:', err, {
                action: form.action || window.location.href,
                operation: 'voucher-group-preview',
            });
            form.dataset.confirmed = '1';
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
        } finally {
            editableControls.forEach((el) => {
                if (el.dataset.prevReadonly === '0') {
                    el.readOnly = false;
                }
                delete el.dataset.prevReadonly;
            });
            if (form.dataset.confirmed !== '1' && submitBtn) {
                submitBtn.disabled = false;
            }
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoucherGroupForm);
} else {
    initVoucherGroupForm();
}
