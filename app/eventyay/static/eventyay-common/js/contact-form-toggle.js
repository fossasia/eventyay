function initContactFormToggle() {
  const enabledCheckbox = document.getElementById('id_settings-contact_form_enabled');
  const emailFields = document.getElementById('contact-form-email-fields');

  if (!enabledCheckbox || !emailFields) {
    return;
  }

  function toggleEmailFields() {
    const show = enabledCheckbox.checked;
    emailFields.style.display = show ? '' : 'none';
    emailFields.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !show;
    });
  }

  enabledCheckbox.addEventListener('change', toggleEmailFields);
  toggleEmailFields();
}

document.addEventListener('DOMContentLoaded', initContactFormToggle);
