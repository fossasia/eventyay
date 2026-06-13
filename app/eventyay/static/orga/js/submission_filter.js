onReady(() => {
    const pendingDiv = document.getElementById('pending')
    const stateInput = document.querySelector('.filter-select input[name="state"]')
    const stateDropdown = stateInput ? stateInput.closest('details.filter-select') : null

    if (pendingDiv && stateDropdown) {
        const menu = stateDropdown.querySelector('.filter-select__menu')
        const separator = document.createElement('div')
        separator.className = 'filter-select__separator'
        pendingDiv.classList.remove('d-none')
        pendingDiv.classList.add('filter-select__pending')
        menu.prepend(separator)
        menu.prepend(pendingDiv)
    }

    document.querySelectorAll('details.filter-select').forEach((details) => {
        const label = details.querySelector('.filter-select__label')
        if (!label) return
        const baseLabel = label.textContent

        const update = () => {
            const optionBoxes = details.querySelectorAll('.filter-select__option input[type="checkbox"]')
            const count = Array.from(optionBoxes).filter((b) => b.checked).length
            label.textContent = count > 0 ? `${baseLabel} (${count})` : baseLabel
        }

        details.querySelectorAll('.filter-select__menu input[type="checkbox"]')
            .forEach((box) => box.addEventListener('change', update))
        update()
    })

    document.addEventListener('click', (event) => {
        document.querySelectorAll('details.filter-select[open]').forEach((details) => {
            if (!details.contains(event.target)) details.removeAttribute('open')
        })
    })
})
