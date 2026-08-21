document.addEventListener("DOMContentLoaded", function() {
    const useFeedbackCheckbox = document.getElementById('id_use_feedback');
    const fieldsets = document.querySelectorAll('fieldset');
    const closeAfterInput = document.getElementById('id_feedback_close_after_days');
    const dialog = document.getElementById('feedback-disable-dialog');
    const btnCancel = document.getElementById('btn-cancel-disable');
    const btnConfirm = document.getElementById('btn-confirm-disable');
    
    function toggleInputs() {
        if (!useFeedbackCheckbox) return;
        const isEnabled = useFeedbackCheckbox.checked;
        
        fieldsets.forEach(fs => {
            if (!fs.contains(useFeedbackCheckbox)) {
                fs.disabled = !isEnabled;
                fs.style.opacity = isEnabled ? '1' : '0.5';
            }
        });
        
        if (closeAfterInput) {
            closeAfterInput.disabled = !isEnabled;
            // Find the parent div wrapping the input to apply opacity
            const wrapper = closeAfterInput.closest('.form-group') || closeAfterInput.closest('.mb-3') || closeAfterInput.parentElement;
            if (wrapper) wrapper.style.opacity = isEnabled ? '1' : '0.5';
        }
    }
    
    if (useFeedbackCheckbox) {
        const initiallyChecked = useFeedbackCheckbox.checked;
        useFeedbackCheckbox.addEventListener('change', toggleInputs);
        toggleInputs();
        
        const form = useFeedbackCheckbox.closest('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                if (initiallyChecked && !useFeedbackCheckbox.checked) {
                    e.preventDefault();
                    if (dialog && typeof dialog.showModal === 'function') {
                        dialog.showModal();
                    } else {
                        // Fallback for browsers that don't support dialog natively
                        const msg = form.getAttribute('data-confirm-msg') || 'Disabling will also hide all the comments. Are you sure you want to proceed?';
                        if (confirm(msg)) {
                            HTMLFormElement.prototype.submit.call(form);
                        } else {
                            useFeedbackCheckbox.checked = true;
                            toggleInputs();
                        }
                    }
                }
            });

            if (btnCancel && btnConfirm) {
                btnCancel.addEventListener('click', function() {
                    dialog.close();
                    useFeedbackCheckbox.checked = true;
                    toggleInputs();
                });
                
                btnConfirm.addEventListener('click', function() {
                    dialog.close();
                    // Safely submit the form
                    HTMLFormElement.prototype.submit.call(form);
                });
            }
        }
    }
});
