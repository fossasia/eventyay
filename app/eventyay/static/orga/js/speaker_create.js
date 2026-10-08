/**
 * Speakers → Add speaker: optional new session, extra session links, and email field.
 */

function refreshRemoveButtons(section) {
  if (!section) return
  const rows = section.querySelectorAll('[data-session-link-row]')
  rows.forEach((row) => {
    const button = row.querySelector('[data-remove-session-link]')
    if (button) {
      button.hidden = rows.length < 2
    }
  })
}

function applySessionSections({ addSessionCheckbox, sessionSection }) {
  const addChecked = Boolean(addSessionCheckbox?.checked)

  if (sessionSection) {
    sessionSection.classList.toggle('d-none', !addChecked)
    sessionSection.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !addChecked
    })
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
  const noEmailCheckbox = root.getElementById?.('id_no_email') || root.querySelector?.('#id_no_email')
  const sessionSection = root.getElementById?.('session_section') || root.querySelector?.('#session_section')
  const existingSessionSection =
    root.getElementById?.('existing_session_section') || root.querySelector?.('#existing_session_section')
  const linkAnotherButton =
    root.getElementById?.('link-another-session') || root.querySelector?.('#link-another-session')
  const rowTemplate =
    root.getElementById?.('session-link-row-template') || root.querySelector?.('#session-link-row-template')
  const emailField = root.getElementById?.('id_email') || root.querySelector?.('#id_email')
  const emailWrapper = emailField ? emailField.closest('.form-group') : null

  if (addSessionCheckbox) {
    addSessionCheckbox.addEventListener('change', () => {
      applySessionSections({ addSessionCheckbox, sessionSection })
    })
  }

  if (existingSessionSection) {
    existingSessionSection.addEventListener('click', (event) => {
      const removeButton = event.target.closest?.('[data-remove-session-link]')
      if (!removeButton || !existingSessionSection.contains(removeButton)) return
      removeButton.closest('[data-session-link-row]')?.remove()
      refreshRemoveButtons(existingSessionSection)
    })
  }

  if (linkAnotherButton && rowTemplate && existingSessionSection) {
    linkAnotherButton.addEventListener('click', () => {
      const links = existingSessionSection.querySelector('[data-session-links]')
      if (!links) return
      links.appendChild(rowTemplate.content.cloneNode(true))
      refreshRemoveButtons(existingSessionSection)
    })
  }

  if (noEmailCheckbox) {
    noEmailCheckbox.addEventListener('change', () => {
      applyEmailState({ noEmailCheckbox, emailField, emailWrapper })
    })
  }

  applySessionSections({ addSessionCheckbox, sessionSection })
  applyEmailState({ noEmailCheckbox, emailField, emailWrapper })
  refreshRemoveButtons(existingSessionSection)
}

initSpeakerCreateForm()
