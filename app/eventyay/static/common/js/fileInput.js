const FILE_INPUT_SELECTOR = 'input[type="file"]'
const CHECKOUT_FILE_INPUT_SELECTOR = '.questions-form input[type="file"]'
const HAS_SELECTION_CLASS = 'file-input-has-selection'
const HAS_ERROR_CLASS = 'file-input-has-error'
const IS_DISABLED_CLASS = 'file-input-is-disabled'
let fileInputIdCounter = 0

const updateFileInput = (input) => {
    const hasSelection = Boolean(input.files?.length)
    const hasError = input.getAttribute('aria-invalid') === 'true' || input.classList.contains('is-invalid')
    const wrapper = input.closest('.eventyay-file-pick-wrapper')
    input.classList.toggle(HAS_SELECTION_CLASS, hasSelection)
    wrapper?.classList.toggle(HAS_SELECTION_CLASS, hasSelection)
    wrapper?.classList.toggle(HAS_ERROR_CLASS, hasError)
    wrapper?.classList.toggle(IS_DISABLED_CLASS, input.disabled)

    const filename = wrapper?.querySelector('.eventyay-file-name')
    if (filename) {
        filename.textContent = hasSelection
            ? Array.from(input.files).map((file) => file.name).join(', ')
            : ''
    }
}

const wrapFileInput = (input) => {
    if (input.closest('.avatar-upload')) return
    if (input.closest('.eventyay-file-pick-wrapper')) return
    if (input.dataset.eventyayFileWrapped === 'true') return
    if (input.dataset.eventyayFileWrapper === 'disabled') return
    if (input.closest('.fileinput-button')) return
    if (input.closest('.btn')) return

    input.dataset.eventyayFileWrapped = 'true'

    const i18nElement = document.getElementById('eventyay-file-input-i18n')
    const chooseLabel = input.dataset.chooseFileLabel || i18nElement?.dataset.chooseFile || 'Choose file'
    const wrapper = document.createElement('div')
    wrapper.className = 'eventyay-file-pick-wrapper'

    if (!input.id) {
        input.id = 'eventyay-file-' + (++fileInputIdCounter)
    }

    const label = document.createElement('label')
    label.setAttribute('for', input.id)
    label.textContent = chooseLabel

    const filename = document.createElement('span')
    filename.className = 'eventyay-file-name text-muted small'
    filename.setAttribute('aria-live', 'polite')

    wrapper.addEventListener('click', (event) => {
        if (event.target !== label && event.target !== input) {
            input.click()
        }
    })

    input.parentNode.insertBefore(wrapper, input)
    wrapper.append(label, filename, input)

    input.addEventListener('change', () => updateFileInput(input))
    input.addEventListener('invalid', () => updateFileInput(input))
    updateFileInput(input)
}

export const initFileInputWrappers = (selector = FILE_INPUT_SELECTOR) => {
    document.querySelectorAll(selector).forEach(wrapFileInput)
}

window.eventyayInitFileInputWrappers = initFileInputWrappers
window.dispatchEvent(new Event('eventyay:file-input-ready'))

const initCheckoutFileInputs = () => initFileInputWrappers(CHECKOUT_FILE_INPUT_SELECTOR)

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCheckoutFileInputs)
} else {
    initCheckoutFileInputs()
}

document.addEventListener('reset', (event) => {
    if (!(event.target instanceof HTMLFormElement)) return

    requestAnimationFrame(() => {
        event.target.querySelectorAll(FILE_INPUT_SELECTOR).forEach(updateFileInput)
    })
})
