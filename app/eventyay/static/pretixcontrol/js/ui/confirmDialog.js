const DIALOG_ID = 'pretix-confirm-dialog';

function gettextSafe(msgid) {
    if (typeof gettext === 'function') {
        return gettext(msgid);
    }
    return msgid;
}

function getDialog() {
    return document.getElementById(DIALOG_ID);
}

function readFormConfirmOptions(form) {
    const dataset = form.dataset;
    return {
        message: dataset.confirm || '',
        title: dataset.confirmTitle || gettextSafe('Please confirm'),
        confirmLabel: dataset.confirmLabel || gettextSafe('Confirm'),
        cancelLabel: dataset.cancelLabel || gettextSafe('Cancel'),
        confirmClass: dataset.confirmClass || 'btn-primary',
    };
}

window.showConfirmDialog = function showConfirmDialog(options) {
    const dialog = getDialog();
    const message = options.message || '';

    if (!dialog || typeof dialog.showModal !== 'function') {
        return Promise.resolve(window.confirm(message));
    }

    const titleEl = document.getElementById('pretix-confirm-dialog-title');
    const messageEl = document.getElementById('pretix-confirm-dialog-message');
    const confirmBtn = document.getElementById('pretix-confirm-dialog-confirm');
    const cancelBtn = document.getElementById('pretix-confirm-dialog-cancel');

    if (!titleEl || !messageEl || !confirmBtn || !cancelBtn) {
        return Promise.resolve(window.confirm(message));
    }

    titleEl.textContent = options.title || gettextSafe('Please confirm');
    messageEl.textContent = message;
    confirmBtn.textContent = options.confirmLabel || gettextSafe('Confirm');
    cancelBtn.textContent = options.cancelLabel || gettextSafe('Cancel');
    confirmBtn.className = 'btn ' + (options.confirmClass || 'btn-primary');

    return new Promise(function (resolve) {
        function finish(confirmed) {
            confirmBtn.removeEventListener('click', onConfirm);
            cancelBtn.removeEventListener('click', onCancel);
            dialog.removeEventListener('cancel', onCancel);
            dialog.removeEventListener('click', onBackdropClick);
            if (dialog.open) {
                dialog.close();
            }
            resolve(confirmed);
        }

        function onConfirm() {
            finish(true);
        }

        function onCancel() {
            finish(false);
        }

        function onBackdropClick(event) {
            if (event.target === dialog) {
                finish(false);
            }
        }

        confirmBtn.addEventListener('click', onConfirm);
        cancelBtn.addEventListener('click', onCancel);
        dialog.addEventListener('cancel', onCancel);
        dialog.addEventListener('click', onBackdropClick);
        dialog.showModal();
        confirmBtn.focus();
    });
};

document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form || !form.matches || !form.matches('form[data-confirm]')) {
        return;
    }

    if (form.dataset.confirmBypass === '1') {
        form.dataset.confirmBypass = '';
        return;
    }

    const options = readFormConfirmOptions(form);
    if (!options.message) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();

    window.showConfirmDialog(options).then(function (confirmed) {
        if (!confirmed) {
            return;
        }
        form.dataset.confirmBypass = '1';
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.submit();
        }
    });
}, true);
