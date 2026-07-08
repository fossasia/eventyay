function initSmtpToggle() {
  const useCustom = document.getElementById('id_email-smtp_use_custom');
  const customFields = document.getElementById('smtp-custom-fields');
  const vendorRadios = document.querySelectorAll('input[name="email-email_vendor"]');
  const smtpFields = document.getElementById('smtp-server-fields');
  const sendgridFields = document.getElementById('sendgrid-fields');

  if (!useCustom || !customFields) {
    return;
  }

  function setDisabled(container, disabled) {
    if (!container) return;
    container.querySelectorAll('input, select, textarea').forEach(el => {
      el.disabled = disabled;
    });
  }

  function toggleVendor() {
    if (!smtpFields || !sendgridFields) {
      return;
    }
    const selected = document.querySelector('input[name="email-email_vendor"]:checked');
    const isSendgrid = selected && selected.value === 'sendgrid';
    smtpFields.style.display = isSendgrid ? 'none' : '';
    sendgridFields.style.display = isSendgrid ? '' : 'none';
    setDisabled(smtpFields, isSendgrid);
    setDisabled(sendgridFields, !isSendgrid);
  }

  function toggleCustom() {
    customFields.style.display = useCustom.checked ? '' : 'none';
    setDisabled(customFields, !useCustom.checked);
    if (useCustom.checked) {
      toggleVendor();
    }
  }

  useCustom.addEventListener('change', toggleCustom);
  for (const radio of vendorRadios) {
    radio.addEventListener('change', toggleVendor);
  }

  toggleCustom();
}

document.addEventListener('DOMContentLoaded', initSmtpToggle);
