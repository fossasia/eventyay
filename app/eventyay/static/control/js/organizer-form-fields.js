function readCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return decodeURIComponent(parts.pop().split(';').shift());
  }
  return '';
}

/**
 * @throws {Error} when the field setting cannot be saved
 */
async function saveField(url, field, value) {
  const token =
    readCookie('eventyay_csrftoken') ||
    readCookie('csrftoken') ||
    readCookie('pretix_csrftoken') ||
    document.querySelector('input[name="csrfmiddlewaretoken"]')?.value ||
    '';
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': token,
    },
    body: JSON.stringify({ field, value }),
  });
  if (!response.ok) {
    throw new Error(`Could not save organiser form field (${response.status})`);
  }
}

function setRequiredState(dropdown, state) {
  dropdown.value = state;
  dropdown.dataset.current = state;
  const wrapper = dropdown.closest('.required-status-wrapper');
  if (wrapper) {
    wrapper.dataset.current = state;
  }
}

function bindRow(row) {
  const url = row.dataset.url;
  const toggle = row.querySelector('.toggle-switch input');
  const dropdown = row.querySelector('.required-status-dropdown');
  if (!toggle || !dropdown || !url) {
    return;
  }

  toggle.addEventListener('change', async () => {
    const previous = !toggle.checked;
    toggle.closest('.toggle-switch').classList.add('loading');
    try {
      await saveField(url, 'active', toggle.checked);
      dropdown.disabled = !toggle.checked;
      dropdown.style.opacity = toggle.checked ? '1' : '0.5';
    } catch (error) {
      console.error('Organiser form field active state was not saved', error);
      toggle.checked = previous;
      window.alert('Could not save this change. Reload the page and try again.');
    } finally {
      toggle.closest('.toggle-switch').classList.remove('loading');
    }
  });

  dropdown.addEventListener('change', async () => {
    if (!toggle.checked) {
      return;
    }
    const previous = dropdown.dataset.current;
    const next = dropdown.value;
    setRequiredState(dropdown, next);
    dropdown.classList.add('loading');
    try {
      await saveField(url, 'required', next);
    } catch (error) {
      console.error('Organiser form field required state was not saved', error);
      setRequiredState(dropdown, previous);
      window.alert('Could not save this change. Reload the page and try again.');
    } finally {
      dropdown.classList.remove('loading');
    }
  });
}

function bindOrganizerRequestFeatureToggle() {
  const form = document.getElementById('organizer-request-feature-toggle');
  const toggle = document.getElementById('organizer-request-enabled');
  const submitButton = form?.querySelector('button[type="submit"]');
  if (!form || !toggle || !submitButton) {
    return;
  }

  const savedState = toggle.dataset.savedState === 'true';
  const updateForm = () => {
    const changed = toggle.checked !== savedState;
    submitButton.disabled = !changed;
    form.dataset.confirm = toggle.checked ? form.dataset.enableConfirm : form.dataset.disableConfirm;
    form.dataset.confirmClass = toggle.checked ? 'btn-primary' : 'btn-danger';
  };

  toggle.addEventListener('change', updateForm);
  updateForm();
}

document.addEventListener('DOMContentLoaded', () => {
  bindOrganizerRequestFeatureToggle();
  document.querySelectorAll('[data-organiser-field]').forEach(bindRow);
});
