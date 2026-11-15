/**
 * Quick setup wizard: keep the required/optional hints of the bank transfer
 * fields in sync with the backend validation (BankTransfer.settings_form_clean).
 *
 * The server renders every one of these labels with its translated "Optional"
 * hint (see render_label in control/forms/renderers.py). This script only hides
 * or shows that hint and adds a "*" marker, so it never needs its own
 * translations. Only the hint is changed, not the HTML "required" attribute,
 * so "Save draft" keeps working.
 */

function setHint(selector, required) {
  const field = document.querySelector(selector)
  const label = field?.closest('.form-group')?.querySelector('label')
  if (!label) return
  const text = label.querySelector('.label-text') ?? label

  // Show or hide the server-rendered, already translated "Optional" hint
  const optional = label.querySelector('.optional')
  if (optional) {
    optional.hidden = required
    const br = optional.previousElementSibling
    if (br?.tagName === 'BR') br.hidden = required
  }

  text.querySelector('.required-indicator')?.remove()
  if (required) {
    const star = document.createElement('span')
    star.className = 'required-indicator text-danger'
    star.setAttribute('aria-hidden', 'true')
    star.textContent = ' *'
    text.append(star)
  }

  // Expose the required state to assistive technology (not valid on a single radio button)
  if (field.type !== 'radio') {
    if (required) {
      field.setAttribute('aria-required', 'true')
    } else {
      field.removeAttribute('aria-required')
    }
  }
}

function updateBankTransferHints() {
  const sepaRadio = document.querySelector(
    "input[name='payment_banktransfer_bank_details_type'][value='sepa']"
  )
  if (!sepaRadio) return
  const isSepa = sepaRadio.checked
  // Account type always has a selection, so show it as required
  setHint("input[name='payment_banktransfer_bank_details_type']", true)
  for (const f of ['name', 'iban', 'bic', 'bank']) {
    setHint(`#id_payment_banktransfer_bank_details_sepa_${f}`, isSepa)
  }
  setHint("textarea[name^='payment_banktransfer_bank_details_']", !isSepa)
}

for (const radio of document.querySelectorAll("input[name='payment_banktransfer_bank_details_type']")) {
  radio.addEventListener('change', updateBankTransferHints)
}
updateBankTransferHints()