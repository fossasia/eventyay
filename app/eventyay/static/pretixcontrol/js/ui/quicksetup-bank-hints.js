/**
 * Quick setup wizard: keep the required/optional hints of the bank transfer
 * fields in sync with the backend validation (BankTransfer.settings_form_clean).
 * Only the hint is changed, not the HTML "required" attribute,
 * so "Save draft" keeps working.
 */
const gettext = window.gettext ?? ((text) => text)

function setHint(selector, required) {
  const field = document.querySelector(selector)
  const label = field?.closest('.form-group')?.querySelector('label')
  // Fall back to the label itself if the .label-text span is missing
  const text = label && (label.querySelector('.label-text') ?? label)
  if (!text) return

  const optional = label.querySelector('.optional')
  if (optional) {
    const br = optional.previousElementSibling
    if (br?.tagName === 'BR') br.remove()
    optional.remove()
  }
  text.querySelectorAll('.required-indicator, .sr-only').forEach((el) => el.remove())

  if (required) {
    const star = document.createElement('span')
    star.className = 'required-indicator text-danger'
    star.setAttribute('aria-hidden', 'true')
    star.textContent = ' *'
    const sr = document.createElement('span')
    sr.className = 'sr-only'
    sr.textContent = `, ${gettext('required')}`
    text.append(star, sr)
  } else {
    const opt = document.createElement('span')
    opt.className = 'optional'
    opt.textContent = gettext('Optional')
    label.append(document.createElement('br'), opt)
  }
}

function updateBankTransferHints() {
  const sepaRadio = document.getElementById('id_payment_banktransfer_bank_details_type_0')
  if (!sepaRadio) return
  const isSepa = sepaRadio.checked
  // Account type always has a selection, so show it as required
  setHint("input[name='payment_banktransfer_bank_details_type']", true)
  // SEPA: holder name, IBAN, BIC and bank name are required
  for (const f of ['name', 'iban', 'bic', 'bank']) {
    setHint(`#id_payment_banktransfer_bank_details_sepa_${f}`, isSepa)
  }
  // Other bank account: free-text details are required
  setHint("textarea[name^='payment_banktransfer_bank_details']", !isSepa)
}

for (const radio of document.querySelectorAll("input[name='payment_banktransfer_bank_details_type']")) {
  radio.addEventListener('change', updateBankTransferHints)
}
updateBankTransferHints()