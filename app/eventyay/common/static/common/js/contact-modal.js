const initContactModal = () => {
    const dialog = document.getElementById('contact-organizer-dialog');
    if (!dialog) return;

    const i18n = dialog.dataset;
    const form = document.getElementById('contact-organizer-form');
    const closeBtn = document.getElementById('contact-modal-close');
    const submitBtn = document.getElementById('contact-submit-btn');
    const successMsg = document.getElementById('contact-success-message');
    const submitLabel = submitBtn ? submitBtn.textContent.trim() : '';

    // Open modal
    document.querySelectorAll('.contact-organizer-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (!dialog.open) {
                dialog.showModal();
            }
        });
    });

    // Close modal
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            dialog.close();
        });
    }

    // Close on backdrop click
    dialog.addEventListener('click', (e) => {
        if (e.target === dialog) {
            dialog.close();
        }
    });

    // Reset form when dialog is closed
    dialog.addEventListener('close', () => {
        if (form) {
            form.style.display = '';
            if (successMsg) successMsg.style.display = 'none';
            form.reset();
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = submitLabel;
            }
            const errorEl = form.querySelector('.contact-form-error');
            if (errorEl) errorEl.remove();
        }
    });

    const showError = (msg) => {
        if (!submitBtn) return;
        const el = document.createElement('p');
        el.className = 'contact-form-error';
        el.textContent = msg;
        submitBtn.parentNode.insertBefore(el, submitBtn);
        submitBtn.disabled = false;
        submitBtn.textContent = submitLabel;
    };

    // Submit form via AJAX
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();

            const errorEl = form.querySelector('.contact-form-error');
            if (errorEl) errorEl.remove();

            const url = form.dataset.url;
            const formData = new FormData(form);

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '…';
            }

            fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
                .then((resp) => resp.json().then((data) => ({ ok: resp.ok, data: data })))
                .then((result) => {
                    if (result.ok && result.data.success) {
                        form.style.display = 'none';
                        if (successMsg) successMsg.style.display = 'block';
                    } else {
                        showError(result.data.error || i18n.msgGenericError);
                    }
                })
                .catch(() => {
                    showError(i18n.msgNetworkError);
                });
        });
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initContactModal);
} else {
    initContactModal();
}
