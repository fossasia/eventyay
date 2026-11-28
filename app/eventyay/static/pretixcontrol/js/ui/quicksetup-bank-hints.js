/**
 * Keep bank transfer required/optional hints in sync with backend
 * validation in both the quickstart wizard and payment settings.
 *
 * Reuse the server-rendered, translated "Optional" hints and add
 * required indicators according to the selected bank account type.
 *
 * Do not set the HTML "required" attribute, so saving incomplete
 * quickstart drafts remains possible.
 */

function setBankTransferHint(selector, required) {
  const fields = document.querySelectorAll(selector)
  if (!fields.length) return
  const label = fields[0].closest('.form-group')?.querySelector('label')
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
  for (const field of fields) {
    if (field.type === 'radio') continue
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
  setBankTransferHint("input[name='payment_banktransfer_bank_details_type']", true)
  for (const f of ['name', 'iban', 'bic', 'bank']) {
    setBankTransferHint(`#id_payment_banktransfer_bank_details_sepa_${f}`, isSepa)
  }
  // I18nTextarea renders one textarea per event language (..._en, ..._de), so match by prefix
  setBankTransferHint("textarea[name^='payment_banktransfer_bank_details_']", !isSepa)
}

function initBankTransferHints() {
  for (const radio of document.querySelectorAll("input[name='payment_banktransfer_bank_details_type']")) {
    radio.addEventListener('change', updateBankTransferHints)
  }
  updateBankTransferHints()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initBankTransferHints)
} else {
  initBankTransferHints()
}
