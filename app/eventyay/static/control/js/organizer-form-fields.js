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
  const token = readCookie('eventyay_csrftoken') || readCookie('csrftoken');
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

function currentOrder(tbody) {
  return Array.from(tbody.querySelectorAll('tr[data-sort-id]'))
    .map((row) => row.dataset.sortId)
    .join(',');
}

function bindDrag(tbody) {
  let dragged = null;

  tbody.addEventListener('dragstart', (event) => {
    const handle = event.target.closest('.dragsort-button');
    if (!handle || !tbody.contains(handle)) {
      return;
    }
    dragged = handle.closest('tr');
    if (!dragged) {
      return;
    }
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', dragged.dataset.sortId || '');
    dragged.classList.add('dragging');
  });

  tbody.addEventListener('dragover', (event) => {
    if (!dragged) {
      return;
    }
    event.preventDefault();
    const target = event.target.closest('tr');
    if (!target || target === dragged || !tbody.contains(target)) {
      return;
    }
    const midpoint = target.getBoundingClientRect().top + target.getBoundingClientRect().height / 2;
    tbody.insertBefore(dragged, event.clientY > midpoint ? target.nextSibling : target);
  });

  tbody.addEventListener('dragend', () => {
    if (dragged) {
      dragged.classList.remove('dragging');
    }
    dragged = null;
  });
}

function bindSave(tbody) {
  const form = document.getElementById('organiser-form-order');
  const input = document.getElementById('organiser-form-order-value');
  if (!form || !input) {
    return;
  }
  form.addEventListener('submit', () => {
    input.value = currentOrder(tbody);
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
  const tbody = document.querySelector('.organiser-form-fields tbody');
  if (!tbody) {
    return;
  }
  bindDrag(tbody);
  bindSave(tbody);
});
