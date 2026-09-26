(function () {
  'use strict';

  function init() {
    const addSessionCheckbox = document.getElementById('id_add_session');
    const linkExistingCheckbox = document.getElementById('id_link_existing_session');
    const noEmailCheckbox = document.getElementById('id_no_email');
    const sessionSection = document.getElementById('session_section');
    const existingSessionSection = document.getElementById('existing_session_section');
    const emailField = document.getElementById('id_email');
    const emailWrapper = emailField ? emailField.closest('.form-group') : null;

    function applySessionSections() {
      const addChecked = addSessionCheckbox && addSessionCheckbox.checked;
      const linkChecked = linkExistingCheckbox && linkExistingCheckbox.checked;

      if (sessionSection) {
        sessionSection.classList.toggle('d-none', !addChecked);
        sessionSection.querySelectorAll('input, select, textarea').forEach(function (el) {
          el.disabled = !addChecked;
        });
      }

      if (existingSessionSection) {
        existingSessionSection.classList.toggle('d-none', !linkChecked);
      }
    }

    if (addSessionCheckbox) {
      addSessionCheckbox.addEventListener('change', function () {
        if (addSessionCheckbox.checked && linkExistingCheckbox) {
          linkExistingCheckbox.checked = false;
        }
        applySessionSections();
      });
    }

    if (linkExistingCheckbox) {
      linkExistingCheckbox.addEventListener('change', function () {
        if (linkExistingCheckbox.checked && addSessionCheckbox) {
          addSessionCheckbox.checked = false;
        }
        applySessionSections();
      });
    }

    function applyEmailState() {
      if (!noEmailCheckbox || !emailField) return;
      const noEmail = noEmailCheckbox.checked;
      if (emailWrapper) {
        emailWrapper.classList.toggle('d-none', noEmail);
      }
      emailField.disabled = noEmail;
    }

    if (noEmailCheckbox) {
      noEmailCheckbox.addEventListener('change', applyEmailState);
    }

    applySessionSections();
    applyEmailState();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
