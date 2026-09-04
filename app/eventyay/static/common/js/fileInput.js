const FILE_INPUT_SELECTOR = 'input[type="file"]'
const CHECKOUT_FILE_INPUT_SELECTOR = '.questions-form input[type="file"]'
const HAS_SELECTION_CLASS = 'file-input-has-selection'
let fileInputIdCounter = 0

const updateFileInput = (input) => {
    const previewRevision =Number(input.dataset.eventyayPreviewRevision || 0) + 1
    input.dataset.eventyayPreviewRevision = previewRevision

    const hasSelection = Boolean(input.files?.length)
    input.classList.toggle(HAS_SELECTION_CLASS, hasSelection)

    const filename = input.closest('.eventyay-file-pick-wrapper')?.querySelector('.eventyay-file-name')
    if (filename) {
        filename.textContent = hasSelection ? input.files[0].name : ''
    }
    const imagePreview = input
        .closest('.eventyay-file-pick-wrapper')
        ?.parentElement
        ?.querySelector('.form-image-preview')

    if (!imagePreview) return

    const image = imagePreview.querySelector('img')
    const imageLink = imagePreview.querySelector('a')

    if (hasSelection && input.files[0].type.startsWith('image/')) {
        const reader = new FileReader()
        reader.onload = (event) => {
            if (Number(input.dataset.eventyayPreviewRevision) !== previewRevision) return

            image.src = event.target.result
            image.classList.remove('d-none')
            imageLink.href = event.target.result
            imageLink.dataset.lightbox = event.target.result
            imagePreview.classList.remove('d-none')
        }
        reader.readAsDataURL(input.files[0])
    } else {
        const initialSrc = image.dataset.initialSrc

        if (initialSrc) {
            image.src = initialSrc
            image.classList.remove('d-none')
            imageLink.href = initialSrc
            imageLink.dataset.lightbox = initialSrc
            imagePreview.classList.remove('d-none')
        } else {
            image.removeAttribute("src")
            image.classList.add("d-none")
            imageLink.removeAttribute("href")
            imagePreview.classList.add("d-none")
        }
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

    const fieldContainer = input.closest('.eventyay-file-pick-wrapper')?.parentElement

    const clearCheckbox = fieldContainer?.querySelector('.form-image-clear input[type="checkbox"]')

    if (clearCheckbox) {
        clearCheckbox.addEventListener('change', () => {
            const imagePreview = fieldContainer.querySelector('.form-image-preview')
            if (!imagePreview) return

            const image = imagePreview.querySelector('img')
            const imageLink = imagePreview.querySelector('a')

            if (clearCheckbox.checked) {
                input.dataset.eventyayPreviewRevision =
                    Number(input.dataset.eventyayPreviewRevision || 0) + 1
                image.removeAttribute('src')
                image.classList.add('d-none')
                imageLink.removeAttribute('href')
                imagePreview.classList.add('d-none')
            } else {
                updateFileInput(input)
            }
        })
    }

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
