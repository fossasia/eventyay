document.addEventListener('DOMContentLoaded', function () {
    const dialog = document.getElementById('contact-organizer-dialog');
    if (!dialog) return;

    const form = document.getElementById('contact-organizer-form');
    const closeBtn = document.getElementById('contact-modal-close');
    const submitBtn = document.getElementById('contact-submit-btn');
    const successMsg = document.getElementById('contact-success-message');
    const submitLabel = submitBtn.textContent.trim();

    // Open modal
    document.querySelectorAll('.contact-organizer-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            if (!dialog.open) {
                dialog.showModal();
            }
        });
    });

    // Close modal
    closeBtn.addEventListener('click', function () {
        dialog.close();
    });

    // Close on backdrop click
    dialog.addEventListener('click', function (e) {
        if (e.target === dialog) {
            dialog.close();
        }
    });

    // Reset form when dialog is closed
    dialog.addEventListener('close', function () {
        form.style.display = '';
        successMsg.style.display = 'none';
        form.reset();
        submitBtn.disabled = false;
        submitBtn.textContent = submitLabel;
        var errorEl = form.querySelector('.contact-form-error');
        if (errorEl) errorEl.remove();
    });

    // Submit form via AJAX
    form.addEventListener('submit', function (e) {
        e.preventDefault();

        var errorEl = form.querySelector('.contact-form-error');
        if (errorEl) errorEl.remove();

        var url = form.dataset.url;
        var formData = new FormData(form);

        submitBtn.disabled = true;
        submitBtn.textContent = '…';

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    return { ok: resp.ok, data: data };
                });
            })
            .then(function (result) {
                if (result.ok && result.data.success) {
                    form.style.display = 'none';
                    successMsg.style.display = '';
                } else {
                    var msg = result.data.error || 'Something went wrong.';
                    var el = document.createElement('p');
                    el.className = 'contact-form-error';
                    el.textContent = msg;
                    submitBtn.parentNode.insertBefore(el, submitBtn);
                    submitBtn.disabled = false;
                    submitBtn.textContent = submitLabel;
                }
            })
            .catch(function () {
                var el = document.createElement('p');
                el.className = 'contact-form-error';
                el.textContent = 'Something went wrong. Please try again.';
                submitBtn.parentNode.insertBefore(el, submitBtn);
                submitBtn.disabled = false;
                submitBtn.textContent = submitLabel;
            });
    });
});
