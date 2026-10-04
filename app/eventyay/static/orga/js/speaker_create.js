/**
 * Speakers → Add speaker: toggle optional session sections and email field.
 */

function applySessionSections({
  addSessionCheckbox,
  linkExistingCheckbox,
  sessionSection,
  existingSessionSection,
}) {
  const addChecked = Boolean(addSessionCheckbox?.checked)
  const linkChecked = Boolean(linkExistingCheckbox?.checked)

  if (sessionSection) {
    sessionSection.classList.toggle('d-none', !addChecked)
    sessionSection.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !addChecked
    })
  }

  // Do not disable the existing-session select: Tom-Select initialises once on
  // page load and ignores later disabled changes on the raw <select>.
  if (existingSessionSection) {
    existingSessionSection.classList.toggle('d-none', !linkChecked)
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
  const linkExistingCheckbox =
    root.getElementById?.('id_link_existing_session') || root.querySelector?.('#id_link_existing_session')
  const noEmailCheckbox = root.getElementById?.('id_no_email') || root.querySelector?.('#id_no_email')
  const sessionSection = root.getElementById?.('session_section') || root.querySelector?.('#session_section')
  const existingSessionSection =
    root.getElementById?.('existing_session_section') || root.querySelector?.('#existing_session_section')
  const emailField = root.getElementById?.('id_email') || root.querySelector?.('#id_email')
  const emailWrapper = emailField ? emailField.closest('.form-group') : null

  const sessionState = {
    addSessionCheckbox,
    linkExistingCheckbox,
    sessionSection,
    existingSessionSection,
  }
  const emailState = { noEmailCheckbox, emailField, emailWrapper }

  if (addSessionCheckbox) {
    addSessionCheckbox.addEventListener('change', () => {
      if (addSessionCheckbox.checked && linkExistingCheckbox) {
        linkExistingCheckbox.checked = false
      }
      applySessionSections(sessionState)
    })
  }

  if (linkExistingCheckbox) {
    linkExistingCheckbox.addEventListener('change', () => {
      if (linkExistingCheckbox.checked && addSessionCheckbox) {
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
