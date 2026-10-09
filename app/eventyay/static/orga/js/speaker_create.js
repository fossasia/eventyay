/**
 * Speakers → Add speaker: new-session toggle, extra session links, and extra speakers.
 */

import { initSpeakerSocialLinksFormset } from '../../common/js/speaker_social_links.js'

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

function applySessionSections({ addSessionCheckbox, sessionSection, existingSessionSection }) {
  const addChecked = Boolean(addSessionCheckbox?.checked)

  if (sessionSection) {
    sessionSection.classList.toggle('d-none', !addChecked)
    sessionSection.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !addChecked
    })
  }

  if (existingSessionSection) {
    existingSessionSection.classList.toggle('is-disabled', addChecked)
    existingSessionSection.querySelectorAll('select, button').forEach((el) => {
      el.disabled = addChecked
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

function appendTemplateRow(template, container) {
  if (!(template instanceof HTMLTemplateElement) || !container) return null
  const row = template.content.cloneNode(true).firstElementChild
  if (!row) return null
  container.appendChild(row)
  return row
}


function bindNoEmailToggles(form) {
  if (!form) return
  const apply = (checkbox) => {
    const emailName = checkbox.name.replace(/no_email$/, 'email')
    const emailField = form.querySelector(`[name="${CSS.escape(emailName)}"]`)
    applyEmailState({
      noEmailCheckbox: checkbox,
      emailField,
      emailWrapper: emailField ? emailField.closest('.form-group') : null,
    })
  }
  form.addEventListener('change', (event) => {
    const checkbox = event.target
    if (!(checkbox instanceof HTMLInputElement) || !checkbox.name?.endsWith('no_email')) return
    apply(checkbox)
  })
  form.querySelectorAll('input[name$="no_email"]').forEach(apply)
}

export function initSpeakerCreateForm(root = document) {
  const addSessionCheckbox = root.getElementById?.('id_add_session') || root.querySelector?.('#id_add_session')
  const sessionSection = root.getElementById?.('session_section') || root.querySelector?.('#session_section')
  const existingSessionSection =
    root.getElementById?.('existing_session_section') || root.querySelector?.('#existing_session_section')
  const linkAnotherButton =
    root.getElementById?.('link-another-session') || root.querySelector?.('#link-another-session')
  const rowTemplate =
    root.getElementById?.('session-link-row-template') || root.querySelector?.('#session-link-row-template')
  const form = root.querySelector?.('#speaker-create-form') || root.querySelector?.('form:not(.mobile-navbar-view-form):not(.d-inline)') || (root.tagName === 'FORM' ? root : null)

  if (existingSessionSection) {
    existingSessionSection.classList.add('session-link-section')
    existingSessionSection.addEventListener('click', (event) => {
      const removeButton = event.target.closest?.('[data-remove-session-link]')
      if (!removeButton || removeButton.disabled || !existingSessionSection.contains(removeButton)) return
      removeButton.closest('[data-session-link-row]')?.remove()
      refreshRemoveButtons(existingSessionSection)
    })
  }

  if (addSessionCheckbox) {
    addSessionCheckbox.addEventListener('change', () => {
      applySessionSections({ addSessionCheckbox, sessionSection, existingSessionSection })
    })
  }

  if (linkAnotherButton && rowTemplate && existingSessionSection) {
    linkAnotherButton.addEventListener('click', () => {
      if (linkAnotherButton.disabled) return
      const links = existingSessionSection.querySelector('[data-session-links]')
      appendTemplateRow(rowTemplate, links)
      refreshRemoveButtons(existingSessionSection)
    })
  }



  bindNoEmailToggles(form)
  root.querySelectorAll?.('[data-social-link-formset]').forEach((formset) => {
    initSpeakerSocialLinksFormset(formset)
  })

  applySessionSections({ addSessionCheckbox, sessionSection, existingSessionSection })
  refreshRemoveButtons(existingSessionSection)
}

initSpeakerCreateForm()
