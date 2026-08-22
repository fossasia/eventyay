const FILE_INPUT_SELECTOR = 'input[type="file"]'
const HAS_SELECTION_CLASS = 'file-input-has-selection'

const updateFileInput = (input) => {
    input.classList.toggle(HAS_SELECTION_CLASS, Boolean(input.files?.length))
}

document.querySelectorAll(FILE_INPUT_SELECTOR).forEach(updateFileInput)

document.addEventListener('change', (event) => {
    if (event.target instanceof HTMLInputElement && event.target.matches(FILE_INPUT_SELECTOR)) {
        updateFileInput(event.target)
    }
})

document.addEventListener('reset', (event) => {
    if (!(event.target instanceof HTMLFormElement)) return

    requestAnimationFrame(() => {
        event.target.querySelectorAll(FILE_INPUT_SELECTOR).forEach(updateFileInput)
    })
})
