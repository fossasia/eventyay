function initSmtpToggle() {
  const useCustom = document.getElementById('id_email-smtp_use_custom');
  const customFields = document.getElementById('smtp-custom-fields');

  if (!useCustom || !customFields) {
    return;
  }

  function setDisabled(container, disabled) {
    if (!container) return;
    container.querySelectorAll('input, select, textarea').forEach(el => {
      el.disabled = disabled;
    });
  }

  function toggleCustom() {
    customFields.style.display = useCustom.checked ? '' : 'none';
    setDisabled(customFields, !useCustom.checked);
  }

  useCustom.addEventListener('change', toggleCustom);
  toggleCustom();
}

document.addEventListener('DOMContentLoaded', initSmtpToggle);
