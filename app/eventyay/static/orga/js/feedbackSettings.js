/**
 * Organizer feedback settings: enable/disable fieldsets and confirm dialog.
 */
export function initFeedbackSettings() {
  const useFeedbackCheckbox = document.getElementById('id_use_feedback');
  if (!useFeedbackCheckbox || useFeedbackCheckbox.dataset.feedbackSettingsInit === 'true') {
    return;
  }
  useFeedbackCheckbox.dataset.feedbackSettingsInit = 'true';

  const fieldsets = document.querySelectorAll('fieldset');
  const closeAfterInput = document.getElementById('id_feedback_close_after_days');
  const dialog = document.getElementById('feedback-disable-dialog');
  const btnCancel = document.getElementById('btn-cancel-disable');
  const btnConfirm = document.getElementById('btn-confirm-disable');

  function toggleInputs() {
    const isEnabled = useFeedbackCheckbox.checked;

    fieldsets.forEach((fs) => {
      if (!fs.contains(useFeedbackCheckbox)) {
        fs.disabled = !isEnabled;
        fs.style.opacity = isEnabled ? '1' : '0.5';
      }
    });

    if (closeAfterInput) {
      closeAfterInput.disabled = !isEnabled;
      const wrapper =
        closeAfterInput.closest('.form-group') ||
        closeAfterInput.closest('.mb-3') ||
        closeAfterInput.parentElement;
      if (wrapper) {
        wrapper.style.opacity = isEnabled ? '1' : '0.5';
      }
    }
  }

  const initiallyChecked = useFeedbackCheckbox.checked;
  useFeedbackCheckbox.addEventListener('change', toggleInputs);
  toggleInputs();

  const form = useFeedbackCheckbox.closest('form');
  if (!form) {
    return;
  }

  form.addEventListener('submit', (event) => {
    if (!(initiallyChecked && !useFeedbackCheckbox.checked)) {
      return;
    }
    event.preventDefault();
    if (dialog && typeof dialog.showModal === 'function') {
      dialog.showModal();
      return;
    }
    const msg =
      form.getAttribute('data-confirm-msg') ||
      'Disabling will also hide all the comments. Are you sure you want to proceed?';
    if (window.confirm(msg)) {
      HTMLFormElement.prototype.submit.call(form);
    } else {
      useFeedbackCheckbox.checked = true;
      toggleInputs();
    }
  });

  if (btnCancel && btnConfirm && dialog) {
    btnCancel.addEventListener('click', () => {
      dialog.close();
      useFeedbackCheckbox.checked = true;
      toggleInputs();
    });

    btnConfirm.addEventListener('click', () => {
      dialog.close();
      HTMLFormElement.prototype.submit.call(form);
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initFeedbackSettings);
} else {
  initFeedbackSettings();
}
