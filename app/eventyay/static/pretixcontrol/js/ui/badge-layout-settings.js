function askUserInput(form, value) {
  return form.querySelector(`input[name="ask_user_fields"][value="${CSS.escape(value)}"]`);
}

function syncRequiredAskUser(form, enabled) {
  form.querySelectorAll('input[name="required_badge_fields"]').forEach((required) => {
    required.disabled = !enabled;
    const askUser = askUserInput(form, required.value);
    if (!askUser) {
      return;
    }
    if (!enabled) {
      required.checked = false;
      askUser.checked = false;
    } else if (required.checked) {
      askUser.checked = true;
    }
    askUser.disabled = !enabled || required.checked;
  });
}

function setCustomizationUi(form, enabled) {
  const fields = form.querySelector('#badge-customization-fields');
  if (fields?.querySelector('table')) {
    fields.hidden = !enabled;
  }

  const editing = form.querySelector('#id_allow_badge_editing');
  if (editing) {
    editing.disabled = !enabled;
    if (!enabled) {
      editing.checked = false;
    }
  }

  syncRequiredAskUser(form, enabled);
}

function initBadgeLayoutSettings() {
  const form = document.querySelector('form[data-badge-layout-settings]');
  const customization = form?.querySelector('#id_allow_customization');
  if (!form || !customization) {
    return;
  }

  customization.addEventListener('change', () => {
    setCustomizationUi(form, customization.checked);
  });
  form.addEventListener('change', (event) => {
    if (event.target?.name === 'required_badge_fields') {
      syncRequiredAskUser(form, customization.checked);
    }
  });
  setCustomizationUi(form, customization.checked);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initBadgeLayoutSettings);
} else {
  initBadgeLayoutSettings();
}
