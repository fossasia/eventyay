const FILE_INPUT_SELECTOR = 'input[type="file"]'
const CHECKOUT_FILE_INPUT_SELECTOR = '.questions-form input[type="file"]'
const HAS_SELECTION_CLASS = 'file-input-has-selection'
let fileInputIdCounter = 0

const updateFileInput = (input) => {
    const hasSelection = Boolean(input.files?.length)
    input.classList.toggle(HAS_SELECTION_CLASS, hasSelection)

    const filename = input.closest('.eventyay-file-pick-wrapper')?.querySelector('.eventyay-file-name')
    if (filename) {
        filename.textContent = hasSelection ? input.files[0].name : ''
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

    const label = document.createElement('label')
    label.setAttribute('for', input.id || '')
    label.textContent = chooseLabel

    const filename = document.createElement('span')
    filename.className = 'eventyay-file-name text-muted small ms-2'

    wrapper.addEventListener('click', (event) => {
        if (event.target !== label && event.target !== input) {
            input.click()
        }
    })

    input.parentNode.insertBefore(wrapper, input)
    wrapper.append(label, filename, input)

    if (!input.id) {
        input.id = 'eventyay-file-' + (++fileInputIdCounter)
        label.setAttribute('for', input.id)
    }

    input.addEventListener('change', () => updateFileInput(input))
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
