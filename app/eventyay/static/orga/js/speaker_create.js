/**
 * Speakers → Add speaker: toggle optional session sections and email field.
 */

function applySessionSections({
  addSessionCheckbox,
  existingSessionSelect,
  sessionSection,
}) {
  const addChecked = Boolean(addSessionCheckbox?.checked)

  if (sessionSection) {
    sessionSection.classList.toggle('d-none', !addChecked)
    sessionSection.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !addChecked
    })
  }

  if (existingSessionSelect) {
    existingSessionSelect.disabled = addChecked
  }
}

function applyEmailState({ noEmailCheckbox, emailField, emailWrapper }) {
  if (!noEmailCheckbox || !emailField) return
  const noEmail = noEmailCheckbox.checked
  if (emailWrapper) {
    emailWrapper.classList.toggle('d-none', noEmail)
  }
  emailField.disabled = noEmail
  emailField.required = !noEmail
}

export function initSpeakerCreateForm(root = document) {
  const addSessionCheckbox = root.getElementById?.('id_add_session') || root.querySelector?.('#id_add_session')
  const existingSessionSelect =
    root.getElementById?.('id_existing_session_id') || root.querySelector?.('#id_existing_session_id')
  const noEmailCheckbox = root.getElementById?.('id_no_email') || root.querySelector?.('#id_no_email')
  const sessionSection = root.getElementById?.('session_section') || root.querySelector?.('#session_section')
  const emailField = root.getElementById?.('id_email') || root.querySelector?.('#id_email')
  const emailWrapper = emailField ? emailField.closest('.form-group') : null

  const sessionState = {
    addSessionCheckbox,
    existingSessionSelect,
    sessionSection,
  }
  const emailState = { noEmailCheckbox, emailField, emailWrapper }

  if (addSessionCheckbox) {
    addSessionCheckbox.addEventListener('change', () => {
      if (addSessionCheckbox.checked && existingSessionSelect) {
        existingSessionSelect.value = ''
      }
      applySessionSections(sessionState)
    })
  }

  if (existingSessionSelect) {
    existingSessionSelect.addEventListener('change', () => {
      if (existingSessionSelect.value && addSessionCheckbox) {
        addSessionCheckbox.checked = false
      }
      applySessionSections(sessionState)
    })
  }

  if (noEmailCheckbox) {
    noEmailCheckbox.addEventListener('change', () => applyEmailState(emailState))
  }

  applySessionSections(sessionState)
  applyEmailState(emailState)
}

initSpeakerCreateForm()
