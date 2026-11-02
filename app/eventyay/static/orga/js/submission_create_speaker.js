/**
 * submission_create_speaker.js
 *
 * Manages the speaker section on the "Create proposal" page:
 *  - Toggles the new-speaker form on/off via the "Add new speaker" checkbox.
 *  - Disables the "Link existing speaker" select while the toggle is on.
 *  - Hides the email field and "Send immediately" when the speaker does not require an email.
 */

function refreshRemoveButtons(section) {
  if (!section) return
  const rows = section.querySelectorAll('[data-speaker-link-row]')
  rows.forEach((row) => {
    const button = row.querySelector('[data-remove-speaker-link]')
    if (button) {
      button.hidden = rows.length < 2
    }
  })
}

function appendTemplateRow(template, container) {
  if (!(template instanceof HTMLTemplateElement) || !container) return null
  const row = template.content.cloneNode(true).firstElementChild
  if (!row) return null
  container.appendChild(row)
  return row
}

function applySpeakerControls({ addSpeakerCheckbox, newSpeakerSection, existingSpeakerSection }) {
  const addChecked = Boolean(addSpeakerCheckbox?.checked)
  const noEmailCheckbox = newSpeakerSection?.querySelector('input[name$="no_email"]') ?? null
  const noEmail = Boolean(noEmailCheckbox?.checked)
  const emailName = noEmailCheckbox?.name?.replace(/no_email$/, 'email')
  const emailField = emailName
    ? newSpeakerSection.querySelector(`[name="${CSS.escape(emailName)}"]`)
    : null
  const emailWrapper = emailField ? emailField.closest('.form-group') : null
  const sendName = noEmailCheckbox?.name?.replace(/no_email$/, 'send_immediately')
  const sendField = sendName
    ? newSpeakerSection.querySelector(`[name="${CSS.escape(sendName)}"]`)
    : null
  const sendWrapper = sendField ? sendField.closest('.form-group') : null

  if (newSpeakerSection) {
    newSpeakerSection.classList.toggle('d-none', !addChecked)
    newSpeakerSection.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !addChecked
    })
  }

  if (emailField) {
    emailWrapper?.classList.toggle('d-none', addChecked && noEmail)
    emailField.disabled = !addChecked || noEmail
    emailField.required = addChecked && !noEmail
  }

  if (sendField) {
    sendWrapper?.classList.toggle('d-none', addChecked && noEmail)
    sendField.disabled = !addChecked || noEmail
  }

  if (existingSpeakerSection) {
    existingSpeakerSection.classList.toggle('is-disabled', addChecked)
    existingSpeakerSection.querySelectorAll('select, button').forEach((el) => {
      el.disabled = addChecked
    })
  }
}

function initSubmissionCreateSpeaker() {
  const form = document.querySelector('form[enctype="multipart/form-data"]')
  const addSpeakerCheckbox = document.getElementById('id_add_new_speaker')
  const newSpeakerSection = document.getElementById('new_speaker_section')
  const existingSpeakerSection = document.getElementById('existing_speaker_section')
  const linkAnotherButton = document.getElementById('link-another-speaker')
  const rowTemplate = document.getElementById('speaker-link-row-template')
  const controls = { addSpeakerCheckbox, newSpeakerSection, existingSpeakerSection }

  const refresh = () => applySpeakerControls(controls)

  existingSpeakerSection?.addEventListener('click', (event) => {
    const removeButton = event.target.closest?.('[data-remove-speaker-link]')
    if (!removeButton || removeButton.disabled || !existingSpeakerSection.contains(removeButton)) return
    removeButton.closest('[data-speaker-link-row]')?.remove()
    refreshRemoveButtons(existingSpeakerSection)
  })

  linkAnotherButton?.addEventListener('click', () => {
    if (linkAnotherButton.disabled) return
    const links = existingSpeakerSection?.querySelector('[data-speaker-links]')
    appendTemplateRow(rowTemplate, links)
    refreshRemoveButtons(existingSpeakerSection)
  })

  addSpeakerCheckbox?.addEventListener('change', refresh)
  form?.addEventListener('change', (event) => {
    const el = event.target
    if (!(el instanceof HTMLInputElement) || !el.name?.endsWith('no_email')) return
    refresh()
  })

  refresh()
  refreshRemoveButtons(existingSpeakerSection)
}

initSubmissionCreateSpeaker()
